"""Redis-backed ingest queue.

Replaces FastAPI BackgroundTasks, which silently loses queued work whenever the
API process restarts (deploy, OOM, crash). Jobs live in a Redis list and are
consumed by a small pool of worker tasks.

Guarantees:
- **Atomic claim** — `UPDATE ... WHERE status='queued'` means exactly one
  consumer wins a job, so duplicate queue entries are harmless.
- **Crash recovery** — on startup, jobs left in queued/running state are pushed
  back onto the queue. Long-running jobs (< 10 min) are left alone so a rolling
  restart doesn't steal live work.
- **Per-project serialisation** still comes from kb_wiki's ingest lock, so two
  different sources of the same project never write the wiki concurrently.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.kb import KBIngestJob, KBSource
from app.models.project import Project
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

QUEUE_KEY = "aipm:kb:ingest_queue"
_RECOVER_LOCK = "aipm:kb:ingest_recover"
_STALE_RUNNING_MINUTES = 10


def _client():
    return redis_client.get_client()


def enqueue_ingest(db: Session, source: KBSource, user_id: Optional[int] = None) -> KBIngestJob:
    """Create a queued job and push it onto the Redis queue."""
    client = _client()
    if client is None:
        raise RuntimeError("Redis 不可用，无法加入摄入队列")

    job = KBIngestJob(
        project_id=source.project_id,
        source_id=source.id,
        status="queued",
        stage="queued",
        progress=0,
    )
    db.add(job)
    source.status = "queued"
    db.commit()
    db.refresh(job)

    client.lpush(QUEUE_KEY, json.dumps({
        "source_id": source.id,
        "job_id": job.id,
        "user_id": user_id,
        "attempt": 0,
    }))
    return job


def queue_depth() -> int:
    client = _client()
    if client is None:
        return 0
    try:
        return int(client.llen(QUEUE_KEY))
    except Exception:
        return 0


def recover_stale(db: Session) -> int:
    """Re-queue jobs orphaned by a previous process. Idempotent across workers."""
    client = _client()
    if client is None:
        return 0
    try:
        if not client.set(_RECOVER_LOCK, "1", nx=True, ex=60):
            return 0
    except Exception:
        return 0

    cutoff = datetime.utcnow() - timedelta(minutes=_STALE_RUNNING_MINUTES)
    jobs = db.query(KBIngestJob).filter(
        KBIngestJob.status.in_(("queued", "running"))
    ).all()

    requeued = 0
    for job in jobs:
        # A job that started moments ago is probably alive in another worker.
        if job.status == "running" and job.started_at and job.started_at > cutoff:
            continue
        job.status = "queued"
        job.stage = "queued"
        job.progress = 0
        if job.source_id:
            src = db.get(KBSource, job.source_id)
            if src:
                src.status = "queued"
        client.lpush(QUEUE_KEY, json.dumps({
            "source_id": job.source_id,
            "job_id": job.id,
            "user_id": None,
            "attempt": 0,
        }))
        requeued += 1

    db.commit()
    if requeued:
        logger.info("Re-queued %s stale ingest job(s) after restart", requeued)
    return requeued


def _pop(timeout: int = 5) -> Optional[Dict[str, Any]]:
    client = _client()
    if client is None:
        time.sleep(timeout)
        return None
    try:
        item = client.brpop(QUEUE_KEY, timeout=timeout)
    except Exception as exc:
        logger.warning("Ingest queue pop failed: %s", exc)
        time.sleep(2)
        return None
    if not item:
        return None
    try:
        return json.loads(item[1])
    except Exception:
        logger.warning("Discarding malformed queue item")
        return None


def _claim(db: Session, job_id: int) -> bool:
    """Atomically move a job from queued → running. Only one caller can win."""
    updated = (
        db.query(KBIngestJob)
        .filter(KBIngestJob.id == job_id, KBIngestJob.status == "queued")
        .update({"status": "running"}, synchronize_session=False)
    )
    db.commit()
    return bool(updated)


async def _process(item: Dict[str, Any]) -> None:
    from app.database import SessionLocal
    from app.services import kb_wiki

    job_id = item.get("job_id")
    if not job_id:
        return

    db = SessionLocal()
    try:
        job = db.get(KBIngestJob, job_id)
        if job is None or job.status in ("succeeded", "failed"):
            return
        if not _claim(db, job_id):
            return  # another worker already took it

        source = db.get(KBSource, job.source_id) if job.source_id else None
        project = db.get(Project, job.project_id)
        if source is None or project is None:
            job = db.get(KBIngestJob, job_id)
            job.status, job.stage, job.progress = "failed", "error", 100
            job.message = "资料或项目已被删除"
            job.finished_at = datetime.utcnow()
            db.commit()
            return

        result = await kb_wiki.ingest_source(
            db, project, source, item.get("user_id"), job_id=job_id
        )

        # Retry once by default when the pipeline fails for a transient reason.
        if result.get("status") == "failed":
            attempt = int(item.get("attempt", 0))
            if attempt < max(0, settings.KB_INGEST_MAX_RETRY):
                client = _client()
                if client is not None:
                    job = db.get(KBIngestJob, job_id)
                    job.status, job.stage, job.progress = "queued", "queued", 0
                    src = db.get(KBSource, item.get("source_id"))
                    if src:
                        src.status = "queued"
                    db.commit()
                    client.lpush(QUEUE_KEY, json.dumps({**item, "attempt": attempt + 1}))
                    logger.info("Retrying ingest job %s (attempt %s)", job_id, attempt + 1)
                    return

        try:
            from app.services import notifier
            await notifier.notify_ingest_result(db, project, source, result)
        except Exception:
            logger.debug("Ingest notification skipped", exc_info=True)
    finally:
        db.close()


async def worker_loop(name: str = "kb-ingest") -> None:
    """Consume the queue forever. Cancelled on shutdown."""
    logger.info("Ingest worker started: %s", name)
    while True:
        try:
            item = await asyncio.to_thread(_pop)
            if item:
                await _process(item)
        except asyncio.CancelledError:
            logger.info("Ingest worker stopping: %s", name)
            raise
        except Exception:
            logger.exception("Ingest worker crashed: %s", name)
            await asyncio.sleep(2)


def start_workers() -> List[asyncio.Task]:
    count = max(1, int(settings.KB_INGEST_WORKERS))
    return [asyncio.create_task(worker_loop(f"kb-ingest-{i + 1}")) for i in range(count)]
