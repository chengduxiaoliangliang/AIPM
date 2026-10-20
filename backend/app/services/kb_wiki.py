"""
LLM Wiki engine.

Instead of chunking sources for retrieval (RAG), every ingest asks the LLM to
integrate the new source into a persistent, interlinked markdown wiki:

    raw source  ->  read & extract  ->  create/update pages  ->  reindex  ->  log

The wiki is a compounding artifact: cross-references, contradictions and
synthesis are written once and kept current, not re-derived per query.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.ai.llm_factory import get_llm, is_llm_configured
from app.models.kb import (
    KBIngestJob, KBLink, KBLintReport, KBPage, KBPageVersion, KBSource,
)
from app.models.project import Project
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

INDEX_SLUG = "index"
LOG_SLUG = "log"
RESERVED_SLUGS = {INDEX_SLUG, LOG_SLUG}

# Ordered for display in the index / structure tree.
PAGE_TYPES: List[str] = ["overview", "topic", "entity", "comparison", "decision", "source"]
TYPE_LABELS: Dict[str, str] = {
    "overview": "综述",
    "topic": "主题",
    "entity": "实体",
    "comparison": "对比",
    "decision": "决策",
    "source": "资料",
    "index": "索引",
    "log": "日志",
}

WIKI_SCHEMA = """你是一个企业项目知识库的「维基维护者」，不是聊天助手。

【知识库结构】
- 这是一个持久化的 Markdown 维基，位于原始资料与用户之间。
- 页面类型：
  - overview  项目综述（全局图景，每个项目最多一个）
  - topic     主题页（某项技术、流程、模块、规范的沉淀）
  - entity    实体页（系统、服务、团队、关键人物、外部依赖）
  - comparison 对比页（方案选型、版本差异、优劣权衡）
  - decision  决策记录（背景、选项、结论、影响）
  - source    单份资料的摘要页
- 页面之间用 [[页面标题]] 建立双链，系统会自动解析并生成反向链接。
- 已存在页面优先「更新」而不是新建重复页面。

【写作要求】
1. 内容必须基于给定资料，不得编造事实；资料未覆盖的部分明确写"资料未提及"。
2. 每页 200~800 字，结构化（小标题、列表、必要时表格），信息密度优先。
3. 主动建立双链：提到已存在的主题/实体时写成 [[标题]]。
4. 如果新资料与已有页面内容冲突，在页面中新增「⚠️ 冲突与待确认」小节说明分歧。
5. 只输出 JSON，不要输出任何解释性文字或 Markdown 代码围栏。"""

INGEST_PROMPT = """请把下面这份新资料整合进项目「{project}」的知识库。

【现有页面目录】
{catalog}

【本次资料】
文件名：{filename}
正文：
\"\"\"
{body}
\"\"\"

请输出如下 JSON：
{{
  "source_summary": "3~5 句话概括这份资料的核心信息",
  "pages": [
    {{
      "action": "create 或 update",
      "title": "页面标题（若更新，必须与现有页面标题完全一致）",
      "type": "overview|topic|entity|comparison|decision|source",
      "summary": "一句话摘要，用于索引页",
      "tags": ["标签1", "标签2"],
      "content": "Markdown 正文，使用 [[其他页面标题]] 建立双链"
    }}
  ],
  "log_entry": "一句话描述本次摄入做了什么"
}}

要求：pages 数量 1~4 个；至少包含一个覆盖本次资料的页面；不要创建 index 或 log 页面。"""

LINT_PROMPT = """你是知识库的质检员。请检查项目「{project}」的维基内容质量。

【页面目录】
{catalog}

【正文摘录】
{excerpts}

请找出以下问题（只报真实存在的问题，不要臆造）：
1. 页面之间互相矛盾的说法
2. 已被新资料取代的过时结论
3. 被反复提及、但没有独立页面的重要概念
4. 明显的信息缺口

输出 JSON：
{{
  "issues": [
    {{
      "type": "contradiction|stale|missing_concept|gap",
      "severity": "high|medium|low",
      "page": "相关页面标题，没有则填 null",
      "detail": "问题描述",
      "suggestion": "修复建议"
    }}
  ]
}}
没有问题就返回 {{"issues": []}}。只输出 JSON。"""


# ─── helpers ─────────────────────────────────────────────────────────────────

def slugify(title: str, fallback: str = "page") -> str:
    s = (title or "").strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", s, flags=re.UNICODE)
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return (s or fallback)[:150]


def extract_wiki_links(content: str) -> List[str]:
    """Return the targets of [[wiki links]] found in a page body."""
    if not content:
        return []
    found = re.findall(r"\[\[([^\[\]|]{1,120})(?:\|[^\[\]]*)?\]\]", content)
    seen, out = set(), []
    for t in found:
        t = t.strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


CHUNK_SIZE = 12000
MAX_CHUNKS = 8


def _split_by_paragraph(text: str, size: int) -> List[str]:
    """Fallback splitter for a single section that is itself too long."""
    out: List[str] = []
    buf = ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) + 2 <= size:
            buf = f"{buf}\n\n{para}" if buf else para
            continue
        if buf:
            out.append(buf)
            buf = ""
        if len(para) > size:
            # A single enormous paragraph (e.g. a table dump): hard-slice it.
            for i in range(0, len(para), size):
                out.append(para[i:i + size])
        else:
            buf = para
    if buf:
        out.append(buf)
    return [c for c in out if c.strip()]


def split_into_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    max_chunks: int = MAX_CHUNKS,
) -> tuple[List[str], bool]:
    """Split a long document into LLM-sized chunks on heading boundaries.

    Short documents stay as a single chunk, so the common path is unchanged.
    Sections are packed greedily up to `chunk_size`.

    Returns (chunks, truncated) — `truncated` is True when the document needed
    more than `max_chunks` pieces, so the caller can tell the user that the tail
    was skipped instead of silently losing it.
    """
    text = (text or "").strip()
    if not text:
        return [], False
    if len(text) <= chunk_size:
        return [text], False

    sections = [s for s in re.split(r"\n(?=#{1,4}\s)", text) if s.strip()]

    chunks: List[str] = []
    buf = ""
    for sec in sections:
        if len(buf) + len(sec) + 1 <= chunk_size:
            buf = f"{buf}\n{sec}" if buf else sec
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(sec) > chunk_size:
            chunks.extend(_split_by_paragraph(sec, chunk_size))
        else:
            buf = sec
    if buf:
        chunks.append(buf)

    truncated = len(chunks) > max_chunks
    return chunks[:max_chunks], truncated


def _parse_json_object(text: str) -> Optional[dict]:
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(s[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


async def _llm_json(system: str, user: str, timeout: float = 180.0) -> Optional[dict]:
    if not (is_llm_configured() and settings.AI_ENABLED):
        return None
    try:
        llm = get_llm(streaming=False)
        if llm is None:
            return None
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)]),
            timeout=timeout,
        )
        raw = resp.content if hasattr(resp, "content") else str(resp)
        parsed = _parse_json_object(raw)
        if parsed is None:
            logger.warning("LLM returned non-JSON output: %s", (raw or "")[:400])
        return parsed
    except Exception as exc:
        logger.warning("LLM JSON call failed: %s", exc)
        return None


def _get_page(db: Session, project_id: int, slug: str) -> Optional[KBPage]:
    return (
        db.query(KBPage)
        .filter(KBPage.project_id == project_id, KBPage.slug == slug)
        .first()
    )


def _upsert_page(db: Session, project_id: int, slug: str, **fields) -> tuple[KBPage, bool]:
    """Create or update a page. Returns (page, created).

    Concurrent ingests can race on the (project_id, slug) unique key, so an
    insert collision falls back to updating the row the other worker created.
    """
    page = _get_page(db, project_id, slug)
    created = page is None
    if created:
        page = KBPage(project_id=project_id, slug=slug)
        db.add(page)

    for k, v in fields.items():
        if v is not None:
            setattr(page, k, v)
    page.updated_at = datetime.utcnow()

    if created:
        savepoint = db.begin_nested()
        try:
            db.flush()
            savepoint.commit()
            return page, True
        except IntegrityError:
            savepoint.rollback()
            page = _get_page(db, project_id, slug)
            if page is None:
                raise
            for k, v in fields.items():
                if v is not None:
                    setattr(page, k, v)
            page.updated_at = datetime.utcnow()
            db.flush()
            return page, False

    db.flush()
    return page, False


def detect_communities(
    node_ids: List[int],
    edges: List[tuple],
    rounds: int = 12,
    seed: int = 42,
) -> Dict[int, int]:
    """Label-propagation community detection.

    Cheap and dependency-free, and good enough to surface "these pages belong
    together" clusters in a wiki of a few hundred pages. The seed keeps the
    result stable across requests so the UI doesn't reshuffle colours.
    """
    import random

    adj: Dict[int, List[int]] = {n: [] for n in node_ids}
    for s, t in edges:
        if s in adj and t in adj:
            adj[s].append(t)
            adj[t].append(s)

    labels = {n: n for n in node_ids}
    rng = random.Random(seed)
    order = list(node_ids)

    for _ in range(rounds):
        changed = False
        rng.shuffle(order)
        for n in order:
            nbrs = adj[n]
            if not nbrs:
                continue
            counts: Dict[int, int] = {}
            for nb in nbrs:
                counts[labels[nb]] = counts.get(labels[nb], 0) + 1
            best = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            if labels[n] != best:
                labels[n] = best
                changed = True
        if not changed:
            break

    groups: Dict[int, List[int]] = {}
    for n, lbl in labels.items():
        groups.setdefault(lbl, []).append(n)

    # Renumber by size so community 0 is always the biggest cluster.
    ordered = sorted(groups.values(), key=len, reverse=True)
    result: Dict[int, int] = {}
    for idx, members in enumerate(ordered):
        for m in members:
            result[m] = idx
    return result


def snapshot_page(
    db: Session,
    page: KBPage,
    change_type: str = "update",
    source_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Optional[KBPageVersion]:
    """Record the page's current state as a new version.

    Skipped for system pages (index/log) and when nothing actually changed, so
    the history stays meaningful instead of filling up with duplicates.
    """
    if page.slug in RESERVED_SLUGS:
        return None

    last = (
        db.query(KBPageVersion)
        .filter(KBPageVersion.page_id == page.id)
        .order_by(KBPageVersion.version_no.desc())
        .first()
    )
    if last and (last.content or "") == (page.content or "") and last.title == page.title:
        return None

    ver = KBPageVersion(
        page_id=page.id,
        project_id=page.project_id,
        version_no=(last.version_no + 1) if last else 1,
        title=page.title,
        summary=page.summary,
        content=page.content,
        tags=page.tags,
        page_type=page.page_type,
        change_type=change_type,
        source_id=source_id,
        created_by=user_id,
    )
    db.add(ver)
    db.flush()
    return ver


# ─── per-project ingest lock ─────────────────────────────────────────────────
_LOCK_PREFIX = "aipm:kb:ingest_lock:"


async def _acquire_project_lock(project_id: int, ttl: int = 900, wait: int = 180) -> bool:
    """Serialise ingests for one project.

    Two concurrent ingests would fight over the same wiki pages (and the shared
    index page), so the second one waits for the first to finish. Returns False
    only when the lock cannot be obtained within `wait` seconds. If Redis is
    unavailable we proceed unlocked rather than blocking the feature.
    """
    client = redis_client.get_client()
    if client is None:
        return True

    key = f"{_LOCK_PREFIX}{project_id}"
    token = f"{time.time()}-{id(object())}"
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            if client.set(key, token, nx=True, ex=ttl):
                return True
        except Exception as exc:
            logger.warning("ingest lock unavailable, proceeding unlocked: %s", exc)
            return True
        await asyncio.sleep(2)
    return False


def _release_project_lock(project_id: int) -> None:
    client = redis_client.get_client()
    if client is None:
        return
    try:
        client.delete(f"{_LOCK_PREFIX}{project_id}")
    except Exception:
        pass


# ─── index / log / links ─────────────────────────────────────────────────────

def rebuild_index(db: Session, project_id: int) -> KBPage:
    """Regenerate index.md from the current page set (deterministic, no LLM)."""
    pages = (
        db.query(KBPage)
        .filter(KBPage.project_id == project_id, KBPage.slug.notin_(RESERVED_SLUGS))
        .order_by(KBPage.page_type.asc(), KBPage.title.asc())
        .all()
    )

    lines = [
        "# 知识库索引",
        "",
        f"> 由系统自动维护 · 共 {len(pages)} 个页面 · 更新于 "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    for ptype in PAGE_TYPES:
        group = [p for p in pages if p.page_type == ptype]
        if not group:
            continue
        lines.append(f"## {TYPE_LABELS.get(ptype, ptype)}（{len(group)}）")
        lines.append("")
        for p in group:
            summary = (p.summary or "").replace("\n", " ").strip()
            lines.append(f"- [[{p.title}]] — {summary}" if summary else f"- [[{p.title}]]")
        lines.append("")

    if not pages:
        lines.append("_暂无页面。上传资料后由 AI 自动生成。_")

    page, _ = _upsert_page(
        db, project_id, INDEX_SLUG,
        title="知识库索引",
        page_type="index",
        summary=f"共 {len(pages)} 个页面的目录",
        content="\n".join(lines),
        generated_by="system",
        status="published",
    )
    return page


def append_log(db: Session, project_id: int, headline: str, detail: str = "") -> KBPage:
    """Append an entry to log.md, newest first."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"## [{stamp}] {headline}\n\n{detail.strip()}\n\n" if detail.strip() else f"## [{stamp}] {headline}\n\n"

    page = _get_page(db, project_id, LOG_SLUG)
    if page is None:
        page = KBPage(
            project_id=project_id,
            slug=LOG_SLUG,
            title="变更日志",
            page_type="log",
            summary="知识库的摄入与体检记录（倒序）",
            content="# 变更日志\n\n" + entry,
            generated_by="system",
        )
        db.add(page)
    else:
        body = page.content or "# 变更日志\n\n"
        marker = body.find("\n\n")
        head = body[: marker + 2] if marker != -1 else "# 变更日志\n\n"
        page.content = head + entry + body[len(head):]
        page.updated_at = datetime.utcnow()
    db.flush()
    return page


def rebuild_links(db: Session, project_id: int) -> int:
    """Re-resolve every [[link]] in the project and rewrite pm_kb_links."""
    pages = db.query(KBPage).filter(KBPage.project_id == project_id).all()
    by_title = {p.title.strip().lower(): p for p in pages}
    by_slug = {p.slug: p for p in pages}

    db.query(KBLink).filter(KBLink.project_id == project_id).delete(synchronize_session=False)
    db.flush()

    count = 0
    for src in pages:
        for target in extract_wiki_links(src.content or ""):
            dst = by_title.get(target.strip().lower()) or by_slug.get(slugify(target))
            if dst and dst.id != src.id:
                db.add(KBLink(
                    project_id=project_id,
                    from_page_id=src.id,
                    to_page_id=dst.id,
                    raw_text=target[:255],
                ))
                count += 1
    db.flush()
    return count


# ─── ingest ──────────────────────────────────────────────────────────────────

def _fallback_plan(source: KBSource, text: str) -> dict:
    """Used when the LLM is unavailable: file the source as a plain page."""
    excerpt = text[:6000]
    return {
        "source_summary": text[:160].replace("\n", " ").strip() or "无摘要",
        "pages": [{
            "action": "create",
            "title": f"资料：{source.original_name}",
            "type": "source",
            "summary": f"{source.original_name}（未经过 AI 加工）",
            "tags": ["未加工", "原始资料"],
            "content": (
                f"# 资料：{source.original_name}\n\n"
                f"> ⚠️ 本条由系统直接归档，未经过大模型提炼（AI 当前不可用）。\n\n"
                f"## 摘录\n\n{excerpt}\n"
            ),
        }],
        "log_entry": "AI 不可用，按原始资料归档",
    }


async def ingest_source(
    db: Session,
    project: Project,
    source: KBSource,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the full ingest pipeline for one source. Always returns a result dict."""
    job = KBIngestJob(
        project_id=project.id,
        source_id=source.id,
        status="running",
        stage="extracting",
        progress=10,
        started_at=datetime.utcnow(),
    )
    db.add(job)
    source.status = "ingesting"
    db.commit()
    job_id = job.id
    source_id = source.id
    project_id = project.id

    # Serialise ingests per project — concurrent runs would fight over the same
    # wiki pages and the shared index page.
    if not await _acquire_project_lock(project_id):
        msg = "该项目知识库正在被其他任务整理，等待超时，请稍后重试"
        job = db.get(KBIngestJob, job_id)
        job.status, job.stage, job.progress = "failed", "error", 100
        job.message, job.finished_at = msg, datetime.utcnow()
        src = db.get(KBSource, source_id)
        if src:
            src.status, src.error_message = "failed", msg
        db.commit()
        return {"job_id": job_id, "status": "failed", "error": msg}

    try:
        text = (source.text_content or "").strip()
        if not text:
            raise ValueError("源文件没有可用文本，无法摄入")

        # ── analyse + write, chunk by chunk ──────────────────────────────
        chunks, truncated = split_into_chunks(text)
        total = len(chunks)

        created = updated = 0
        used_llm = False
        summaries: List[str] = []
        log_bits: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            job = db.get(KBIngestJob, job_id)
            job.stage = "analysing" if total == 1 else f"analysing ({idx}/{total})"
            job.progress = 20 + int(45 * (idx - 1) / total)
            db.commit()

            # Re-read the catalog every round so later chunks update the pages
            # created by earlier ones instead of duplicating them.
            existing = (
                db.query(KBPage)
                .filter(KBPage.project_id == project_id, KBPage.slug.notin_(RESERVED_SLUGS))
                .order_by(KBPage.updated_at.desc())
                .limit(60)
                .all()
            )
            catalog = "\n".join(
                f"- {p.title} [{p.page_type}]：{(p.summary or '')[:80]}" for p in existing
            ) or "（当前知识库为空）"

            plan = await _llm_json(
                WIKI_SCHEMA,
                INGEST_PROMPT.format(
                    project=project.name,
                    catalog=catalog,
                    filename=source.original_name,
                    body=chunk,
                ),
            )
            if plan is not None:
                used_llm = True
            elif idx == 1:
                # Only the first chunk falls back to plain filing — retrying the
                # fallback for every chunk would flood the wiki with stub pages.
                plan = _fallback_plan(source, chunk)
            else:
                plan = None

            if not plan:
                continue

            summaries.append((plan.get("source_summary") or "").strip())
            if plan.get("log_entry"):
                log_bits.append(str(plan["log_entry"]).strip())

            job = db.get(KBIngestJob, job_id)
            job.stage = "writing" if total == 1 else f"writing ({idx}/{total})"
            job.progress = 20 + int(60 * idx / total)
            db.commit()

            for spec in (plan.get("pages") or [])[:6]:
                title = (spec.get("title") or "").strip()
                if not title:
                    continue
                slug = slugify(title)
                if slug in RESERVED_SLUGS:
                    continue
                ptype = spec.get("type") if spec.get("type") in PAGE_TYPES else "topic"
                tags = spec.get("tags") or []
                page, was_created = _upsert_page(
                    db, project_id, slug,
                    title=title[:255],
                    page_type=ptype,
                    summary=(spec.get("summary") or "")[:1000],
                    content=spec.get("content") or "",
                    tags=",".join(tags)[:255] if isinstance(tags, list) else str(tags)[:255],
                    source_ids=json.dumps([source_id], ensure_ascii=False),
                    generated_by="llm" if used_llm else "system",
                    status="published",
                    created_by=user_id,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
                    try:
                        ids = set(json.loads(page.source_ids or "[]"))
                    except Exception:
                        ids = set()
                    ids.add(source_id)
                    page.source_ids = json.dumps(sorted(ids), ensure_ascii=False)

                snapshot_page(
                    db, page,
                    "create" if was_created else "update",
                    source_id=source_id,
                    user_id=user_id,
                )
            db.flush()

        link_count = rebuild_links(db, project_id)
        rebuild_index(db, project_id)

        summary_text = " ".join(s for s in summaries if s)[:800]
        detail = f"{summary_text}\n\n" if summary_text else ""
        detail += f"新增 {created} 页 / 更新 {updated} 页 / 解析 {link_count} 条双链"
        if total > 1:
            detail += f"\n文档较长（{len(text)} 字符），已分 {total} 段摄入"
        if truncated:
            detail += f"\n⚠️ 超出单次处理上限（{MAX_CHUNKS} 段），尾部内容未摄入"

        append_log(db, project_id, f"ingest | {source.original_name}", detail)

        source = db.get(KBSource, source_id)
        source.status = "indexed"
        source.error_message = None

        job = db.get(KBIngestJob, job_id)
        job.status, job.stage, job.progress = "succeeded", "done", 100
        job.pages_created, job.pages_updated = created, updated
        job.used_llm = "true" if used_llm else "false"
        job.message = (summary_text or (log_bits[0] if log_bits else ""))[:2000]
        job.finished_at = datetime.utcnow()
        db.commit()

        return {
            "job_id": job_id,
            "status": "succeeded",
            "pages_created": created,
            "pages_updated": updated,
            "links": link_count,
            "used_llm": used_llm,
            "chunks": total,
            "summary": summary_text,
        }

    except Exception as exc:
        logger.exception("ingest failed for source %s", source_id)
        db.rollback()
        try:
            job = db.get(KBIngestJob, job_id)
            if job:
                job.status, job.stage, job.progress = "failed", "error", 100
                job.message = str(exc)[:2000]
                job.finished_at = datetime.utcnow()
            src = db.get(KBSource, source_id)
            if src:
                src.status = "failed"
                src.error_message = str(exc)[:2000]
            db.commit()
        except Exception:
            db.rollback()
        return {"job_id": job_id, "status": "failed", "error": str(exc)}

    finally:
        _release_project_lock(project_id)


# ─── lint ────────────────────────────────────────────────────────────────────

def _deterministic_issues(db: Session, project_id: int) -> tuple[List[dict], dict]:
    pages = db.query(KBPage).filter(KBPage.project_id == project_id).all()
    real = [p for p in pages if p.slug not in RESERVED_SLUGS]
    links = db.query(KBLink).filter(KBLink.project_id == project_id).all()

    inbound: Dict[int, int] = {}
    outbound: Dict[int, int] = {}
    for l in links:
        inbound[l.to_page_id] = inbound.get(l.to_page_id, 0) + 1
        outbound[l.from_page_id] = outbound.get(l.from_page_id, 0) + 1

    titles = {p.title.strip().lower() for p in pages}
    issues: List[dict] = []

    if not real:
        issues.append({
            "type": "empty_wiki", "severity": "high", "page": None,
            "detail": "该项目知识库还没有任何页面",
            "suggestion": "上传资料并执行摄入，AI 会自动生成页面",
        })

    for p in real:
        if inbound.get(p.id, 0) == 0:
            issues.append({
                "type": "orphan", "severity": "low", "page": p.title,
                "detail": "没有任何页面链接到本页，容易成为孤岛",
                "suggestion": "在相关主题页中添加指向本页的 [[双链]]",
            })
        if len((p.content or "").strip()) < 120:
            issues.append({
                "type": "thin_content", "severity": "medium", "page": p.title,
                "detail": f"正文仅 {len((p.content or '').strip())} 字符，信息量偏低",
                "suggestion": "补充细节或合并到相关主题页",
            })
        for target in extract_wiki_links(p.content or ""):
            if target.strip().lower() not in titles:
                issues.append({
                    "type": "broken_link", "severity": "medium", "page": p.title,
                    "detail": f"链接目标「{target}」不存在",
                    "suggestion": "创建该页面，或修正链接文字",
                })

    if not any(p.page_type == "overview" for p in real):
        issues.append({
            "type": "no_overview", "severity": "medium", "page": None,
            "detail": "缺少项目综述页，缺少全局图景",
            "suggestion": "手动新建一个 overview 页面，或在摄入时要求 AI 生成",
        })

    sources = db.query(KBSource).filter(KBSource.project_id == project_id).all()
    unindexed = [s for s in sources if s.status not in ("indexed",)]
    if unindexed:
        issues.append({
            "type": "unindexed_source", "severity": "medium", "page": None,
            "detail": f"{len(unindexed)} 份资料尚未完成摄入",
            "suggestion": "在「资料」列表中对其执行「AI 摄入」",
        })
    failed = [s for s in sources if s.status == "failed" or (s.char_count or 0) == 0]
    if failed:
        issues.append({
            "type": "extraction_failed", "severity": "high", "page": None,
            "detail": f"{len(failed)} 份资料未能提取到有效文本",
            "suggestion": "检查是否为扫描版 PDF，或改为手动录入",
        })

    stats = {
        "pages": len(real),
        "sources": len(sources),
        "indexed_sources": len([s for s in sources if s.status == "indexed"]),
        "links": len(links),
        "orphans": len([i for i in issues if i["type"] == "orphan"]),
        "broken_links": len([i for i in issues if i["type"] == "broken_link"]),
        "by_type": {t: len([p for p in real if p.page_type == t]) for t in PAGE_TYPES},
    }
    return issues, stats


async def lint_project(
    db: Session,
    project: Project,
    user_id: Optional[int] = None,
) -> KBLintReport:
    issues, stats = _deterministic_issues(db, project.id)

    pages = (
        db.query(KBPage)
        .filter(KBPage.project_id == project.id, KBPage.slug.notin_(RESERVED_SLUGS))
        .order_by(KBPage.updated_at.desc())
        .limit(25)
        .all()
    )
    if pages and is_llm_configured() and settings.AI_ENABLED:
        catalog = "\n".join(f"- {p.title} [{p.page_type}]：{(p.summary or '')[:80]}" for p in pages)
        excerpts = "\n\n".join(
            f"### {p.title}\n{(p.content or '')[:1200]}" for p in pages[:12]
        )
        result = await _llm_json(
            WIKI_SCHEMA,
            LINT_PROMPT.format(project=project.name, catalog=catalog, excerpts=excerpts),
        )
        if result:
            for it in (result.get("issues") or [])[:20]:
                if not isinstance(it, dict) or not it.get("detail"):
                    continue
                issues.append({
                    "type": it.get("type") or "gap",
                    "severity": it.get("severity") if it.get("severity") in ("high", "medium", "low") else "medium",
                    "page": it.get("page"),
                    "detail": str(it.get("detail"))[:500],
                    "suggestion": str(it.get("suggestion") or "")[:500],
                    "source": "llm",
                })

    for i in issues:
        i.setdefault("source", "rule")

    penalty = {"high": 12, "medium": 6, "low": 2}
    score = 100 - sum(penalty.get(i.get("severity", "low"), 2) for i in issues)
    score = max(0, min(100, score))

    report = KBLintReport(
        project_id=project.id,
        score=score,
        issues_json=json.dumps(issues, ensure_ascii=False),
        stats_json=json.dumps(stats, ensure_ascii=False),
        created_by=user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    append_log(
        db, project.id,
        "lint | 知识库体检",
        f"健康分 {score}，发现 {len(issues)} 个问题"
        f"（高 {len([i for i in issues if i.get('severity') == 'high'])} / "
        f"中 {len([i for i in issues if i.get('severity') == 'medium'])} / "
        f"低 {len([i for i in issues if i.get('severity') == 'low'])}）",
    )
    db.commit()
    return report


# ─── knowledge-base Q&A ──────────────────────────────────────────────────────

ASK_SELECT_PROMPT = """你是知识库检索器。给定用户问题和页面目录，选出最相关的页面标题。

只输出 JSON：{{"pages": ["标题1", "标题2"]}}
- 最多 {limit} 个，按相关度降序
- 标题必须与目录中的完全一致
- 若没有任何页面相关，返回 {{"pages": []}}
- 不要输出任何解释文字"""

ASK_ANSWER_PROMPT = """你是项目知识库助手。请仅依据下面提供的页面内容回答问题。

【规则】
1. 只能使用给定页面的信息，不得编造。信息不足时明确说明「知识库中未涵盖」。
2. 每个关键结论后标注来源，格式为：[页面标题]
3. 用 Markdown 排版，简洁、有条理、有信息密度。
4. 如果多个页面存在冲突说法，要指出分歧。

【问题】
{question}

【页面内容】
{pages}

请直接输出答案，不要复述这些规则。"""


async def _llm_text(system: str, user: str, timeout: float = 180.0) -> Optional[str]:
    """Plain-text LLM call (no JSON parsing)."""
    if not (is_llm_configured() and settings.AI_ENABLED):
        return None
    try:
        llm = get_llm(streaming=False)
        if llm is None:
            return None
        from langchain_core.messages import HumanMessage, SystemMessage

        resp = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)]),
            timeout=timeout,
        )
        raw = resp.content if hasattr(resp, "content") else str(resp)
        return (raw or "").strip() or None
    except Exception as exc:
        logger.warning("LLM text call failed: %s", exc)
        return None


def _query_tokens(question: str) -> List[str]:
    """Tokenise a question for cheap lexical pre-filtering (CJK bigrams + words)."""
    q = (question or "").lower()
    toks = set(re.findall(r"[a-z]{2,}", q))
    for run in re.findall(r"[\u4e00-\u9fff]+", q):
        if len(run) <= 4:
            toks.add(run)
        for i in range(len(run) - 1):
            toks.add(run[i:i + 2])
    return [t for t in toks if t]


def _keyword_candidates(db: Session, project_id: int, question: str, limit: int = 12) -> List[KBPage]:
    pages = (
        db.query(KBPage)
        .filter(KBPage.project_id == project_id, KBPage.slug.notin_(RESERVED_SLUGS))
        .all()
    )
    if not pages:
        return []

    tokens = _query_tokens(question)
    scored: List[tuple] = []
    for p in pages:
        title = (p.title or "").lower()
        summary = (p.summary or "").lower()
        body = (p.content or "")[:4000].lower()
        score = 0
        for t in tokens:
            if t in title:
                score += 6
            elif t in summary:
                score += 3
            elif t in body:
                score += 1
        scored.append((score, p))

    scored.sort(key=lambda x: (-x[0], -(x[1].updated_at.timestamp() if x[1].updated_at else 0)))
    return [p for s, p in scored[:limit]]


def _gather_candidates(
    db: Session,
    projects: List[Project],
    question: str,
    per_project: int = 8,
    total: int = 16,
) -> List[KBPage]:
    """Collect candidate pages across one or more projects."""
    out: List[KBPage] = []
    seen = set()
    for proj in projects:
        for page in _keyword_candidates(db, proj.id, question, limit=per_project):
            if page.id in seen:
                continue
            seen.add(page.id)
            out.append(page)
    return out[:total]


async def _select_pages(question: str, candidates: List[KBPage]) -> List[KBPage]:
    """Let the model narrow the candidate set; fall back to the top few."""
    if is_llm_configured() and settings.AI_ENABLED:
        catalog = "\n".join(
            f"- {p.title}：{(p.summary or '')[:80]}" for p in candidates
        )
        picked = await _llm_json(
            WIKI_SCHEMA,
            ASK_SELECT_PROMPT.format(limit=6)
            + f"\n\n【页面目录】\n{catalog}\n\n【问题】\n{question}",
        )
        if picked and isinstance(picked.get("pages"), list):
            wanted = {str(t).strip().lower() for t in picked["pages"]}
            chosen = [p for p in candidates if p.title.strip().lower() in wanted]
            if chosen:
                return chosen
    return candidates[:4]


def _answer_body(selected: List[KBPage]) -> str:
    return "\n\n".join(
        f"### {p.title}\n{(p.content or '')[:3000]}" for p in selected[:5]
    )


def _fallback_answer(selected: List[KBPage]) -> str:
    return (
        "> ⚠️ 大模型暂不可用，以下是与问题最相关的页面，请直接查阅：\n\n"
        + "\n".join(
            f"- **{p.title}** — {(p.summary or (p.content or '')[:100]).strip()}"
            for p in selected
        )
    )


def _citations(pages: List[KBPage], proj_names: Dict[int, str]) -> List[dict]:
    out = []
    for p in pages:
        item = {"id": p.id, "title": p.title, "page_type": p.page_type}
        if len(proj_names) > 1:
            item["project"] = proj_names.get(p.project_id, "")
        out.append(item)
    return out


async def answer_question(
    db: Session,
    projects: List[Project],
    question: str,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Answer a question from one or more wikis, with citations."""
    if isinstance(projects, Project):
        projects = [projects]
    proj_names = {p.id: p.name for p in projects}

    candidates = _gather_candidates(db, projects, question)
    if not candidates:
        return {
            "answer": "知识库中还没有可用的页面，无法回答。请先上传资料并完成摄入。",
            "citations": [], "used_llm": False,
        }

    selected = await _select_pages(question, candidates)

    answer = await _llm_text(
        WIKI_SCHEMA,
        ASK_ANSWER_PROMPT.format(question=question, pages=_answer_body(selected)),
    )

    used_llm = answer is not None
    if not used_llm:
        answer = _fallback_answer(selected)

    cited = [p for p in selected if p.title and p.title in (answer or "")]
    if not cited:
        cited = selected[:3]

    return {
        "answer": answer,
        "citations": _citations(cited, proj_names),
        "used_llm": used_llm,
    }


async def stream_answer(
    db: Session,
    projects: List[Project],
    question: str,
    user_id: Optional[int] = None,
):
    """Yield SSE-ready events for a streamed answer.

    Event shapes:
      {"status": "retrieving"}
      {"status": "citations", "citations": [...]}
      {"status": "streaming", "content": "..."}
      {"status": "finished", "content": ""}
    """
    if isinstance(projects, Project):
        projects = [projects]
    proj_names = {p.id: p.name for p in projects}

    yield {"status": "retrieving"}

    candidates = _gather_candidates(db, projects, question)
    if not candidates:
        yield {
            "status": "streaming",
            "content": "知识库中还没有可用的页面，无法回答。请先上传资料并完成摄入。",
        }
        yield {"status": "finished", "content": ""}
        return

    selected = await _select_pages(question, candidates)
    yield {"status": "citations", "citations": _citations(selected[:5], proj_names)}

    llm = get_llm(streaming=True) if (is_llm_configured() and settings.AI_ENABLED) else None
    if llm is None:
        yield {"status": "streaming", "content": _fallback_answer(selected)}
        yield {"status": "finished", "content": ""}
        return

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = ASK_ANSWER_PROMPT.format(question=question, pages=_answer_body(selected))
        async for chunk in llm.astream([
            SystemMessage(content=WIKI_SCHEMA),
            HumanMessage(content=prompt),
        ]):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            if text:
                yield {"status": "streaming", "content": text}
    except Exception as exc:
        logger.warning("KB stream answer failed: %s", exc)
        yield {"status": "streaming", "content": f"\n\n> ⚠️ 生成中断：{exc}"}

    yield {"status": "finished", "content": ""}
