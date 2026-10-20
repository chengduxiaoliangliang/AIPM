"""Periodic knowledge-base health check.

Runs inside the API process on the shared event loop. A Redis lock makes sure
only one worker actually performs the sweep, even when uvicorn runs several
workers against the same Redis.

Configure via env:
    KB_LINT_ENABLED=true
    KB_LINT_INTERVAL_HOURS=24     # 0 disables
    KB_LINT_INITIAL_DELAY_MIN=10  # grace period after boot
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import func

from app.config import settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_LOCK_KEY = "aipm:kb:lint_scheduler"


async def _run_once() -> int:
    """Lint every project that has pages. Returns how many were checked."""
    from app.database import SessionLocal
    from app.models.kb import KBPage
    from app.models.project import Project
    from app.services import kb_wiki

    client = redis_client.get_client()
    if client is not None:
        ttl = max(60, int(settings.KB_LINT_INTERVAL_HOURS * 3600 * 0.8))
        try:
            if not client.set(_LOCK_KEY, "1", nx=True, ex=ttl):
                logger.info("KB lint skipped — another worker holds the lock")
                return 0
        except Exception as exc:
            logger.warning("KB lint lock unavailable, running anyway: %s", exc)

    db = SessionLocal()
    checked = 0
    try:
        projects = db.query(Project).all()
        for proj in projects:
            page_count = db.query(func.count(KBPage.id)).filter(
                KBPage.project_id == proj.id,
                KBPage.slug.notin_(("index", "log")),
            ).scalar() or 0
            if page_count == 0:
                continue
            try:
                report = await kb_wiki.lint_project(db, proj, None)
                checked += 1
                logger.info(
                    "KB lint %s: score=%s", proj.name, report.score
                )

                # Only automatic sweeps notify — manual "体检" clicks stay quiet.
                try:
                    import json

                    from app.services import notifier
                    issues = json.loads(report.issues_json or "[]")
                    await notifier.notify_lint_alert(db, proj, report, issues)
                except Exception:
                    logger.debug("Lint notification skipped", exc_info=True)
            except Exception:
                logger.exception("KB lint failed for project %s", proj.id)
                db.rollback()
    finally:
        db.close()
    return checked


async def scheduler_loop() -> None:
    """Background task started from the FastAPI lifespan."""
    interval_h = settings.KB_LINT_INTERVAL_HOURS
    if not settings.KB_LINT_ENABLED or interval_h <= 0:
        logger.info("KB lint scheduler disabled")
        return

    delay = max(0, settings.KB_LINT_INITIAL_DELAY_MIN) * 60
    logger.info(
        "KB lint scheduler started: first run in %ss, then every %sh",
        delay, interval_h,
    )
    if delay:
        await asyncio.sleep(delay)

    while True:
        started = datetime.utcnow()
        try:
            checked = await _run_once()
            logger.info("KB lint sweep finished: %s project(s)", checked)
        except asyncio.CancelledError:
            logger.info("KB lint scheduler cancelled")
            raise
        except Exception:
            logger.exception("KB lint sweep crashed")
        logger.debug("sweep started at %s", started)
        await asyncio.sleep(interval_h * 3600)
