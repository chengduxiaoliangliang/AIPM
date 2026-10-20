"""
Knowledge base API — LLM Wiki mode.

Routes
  GET    /kb/projects                      per-project knowledge stats
  GET    /kb/projects/{pid}/structure      page tree grouped by type
  GET    /kb/projects/{pid}/graph          nodes + edges for the wiki graph
  GET    /kb/projects/{pid}/export         zip of all markdown pages
  GET    /kb/projects/{pid}/pages          list pages
  POST   /kb/projects/{pid}/pages          create page manually
  GET    /kb/pages/{page_id}               page detail + links + sources
  PUT    /kb/pages/{page_id}               update page
  DELETE /kb/pages/{page_id}               delete page
  GET    /kb/projects/{pid}/sources        list uploaded sources
  POST   /kb/projects/{pid}/sources        upload one or more files
  GET    /kb/sources/{sid}/download        download the original file
  DELETE /kb/sources/{sid}                 delete source + file
  POST   /kb/sources/{sid}/ingest          run the ingest pipeline (async)
  GET    /kb/projects/{pid}/jobs           ingest job history / polling
  POST   /kb/projects/{pid}/lint           run a health check
  GET    /kb/projects/{pid}/lint/latest    latest health-check report
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.tools import PermissionScopedTools
from app.api.deps import get_current_user
from app.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.database import get_db
from app.models.kb import (
    KBIngestJob, KBLink, KBLintReport, KBNotifyPref, KBPage, KBPageVersion,
    KBSource,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.kb import (
    KBAskCitation, KBAskRequest, KBAskResponse,
    KBIngestJobOut, KBLintOut, KBNotifyPrefIn, KBNotifyPrefOut, KBPageBrief,
    KBPageOut, KBPageUpsert, KBPageVersionBrief, KBPageVersionOut,
    KBProjectSummary, KBSourceOut,
)
from app.services import kb_extract, kb_queue, kb_wiki

logger = logging.getLogger(__name__)

router = APIRouter()

_RESERVED = {"index", "log"}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _kb_root() -> Path:
    root = Path(settings.KB_STORAGE_DIR)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _is_admin(user: User) -> bool:
    return user.is_superuser or any(r.code in ("ADMIN", "PM") for r in user.roles)


def _assert_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise NotFoundException("项目不存在")
    if not _is_admin(user):
        if project_id not in PermissionScopedTools.get_user_accessible_project_ids(user, db):
            raise ForbiddenException("无权访问该项目的知识库")
    return project


# ─── page-level access control ───────────────────────────────────────────────

def _role_codes(user: User) -> set:
    return {r.code for r in user.roles}


def _can_view_page(page: KBPage, user: User) -> bool:
    """Whether `user` may read this page (project access is checked separately)."""
    if user.is_superuser:
        return True
    roles = _role_codes(user)
    if "ADMIN" in roles:
        return True

    vis = page.visibility or "project"
    if vis == "project":
        return True
    if page.created_by == user.id:
        return True
    if vis == "private":
        return False
    if "PM" in roles:
        return True
    allowed = {s.strip() for s in (page.allowed_roles or "").split(",") if s.strip()}
    return bool(roles & allowed)


def _can_edit_page(page: KBPage, user: User) -> bool:
    if user.is_superuser:
        return True
    roles = _role_codes(user)
    if "ADMIN" in roles or "PM" in roles:
        return True
    return page.created_by == user.id


def _visible_pages(
    db: Session,
    project_id: int,
    user: User,
    include_reserved: bool = False,
) -> List[KBPage]:
    q = db.query(KBPage).filter(KBPage.project_id == project_id)
    if not include_reserved:
        q = q.filter(KBPage.slug.notin_(_RESERVED))
    return [p for p in q.all() if _can_view_page(p, user)]


def _source_out(s: KBSource) -> KBSourceOut:    return KBSourceOut(
        id=s.id, project_id=s.project_id, original_name=s.original_name,
        mime_type=s.mime_type, size_bytes=s.size_bytes or 0,
        char_count=s.char_count or 0, status=s.status,
        extraction_note=s.extraction_note, error_message=s.error_message,
        uploaded_by=s.uploaded_by, created_at=s.created_at,
    )


_VISIBILITIES = ("project", "restricted", "private")


def _clean_visibility(value: Optional[str]) -> str:
    return value if value in _VISIBILITIES else "project"


def _page_brief(p: KBPage) -> KBPageBrief:
    return KBPageBrief(
        id=p.id, slug=p.slug, title=p.title, page_type=p.page_type,
        summary=p.summary, tags=p.tags, updated_at=p.updated_at,
        visibility=p.visibility or "project",
        allowed_roles=p.allowed_roles,
        created_by=p.created_by,
    )


# ─── project overview ────────────────────────────────────────────────────────

@router.get("/projects", response_model=ResponseModel[List[KBProjectSummary]])
def list_kb_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Knowledge-base stats for every project the user can see."""
    if _is_admin(current_user):
        projects = db.query(Project).order_by(Project.updated_at.desc()).all()
    else:
        ids = PermissionScopedTools.get_user_accessible_project_ids(current_user, db)
        projects = db.query(Project).filter(Project.id.in_(ids)).all() if ids else []

    result: List[KBProjectSummary] = []
    for p in projects:
        pages = db.query(func.count(KBPage.id)).filter(
            KBPage.project_id == p.id, KBPage.slug.notin_(_RESERVED)
        ).scalar() or 0
        sources = db.query(func.count(KBSource.id)).filter(KBSource.project_id == p.id).scalar() or 0
        indexed = db.query(func.count(KBSource.id)).filter(
            KBSource.project_id == p.id, KBSource.status == "indexed"
        ).scalar() or 0
        links = db.query(func.count(KBLink.id)).filter(KBLink.project_id == p.id).scalar() or 0
        last_page = db.query(func.max(KBPage.updated_at)).filter(
            KBPage.project_id == p.id, KBPage.slug.notin_(_RESERVED)
        ).scalar()
        last_source = db.query(func.max(KBSource.created_at)).filter(
            KBSource.project_id == p.id
        ).scalar()
        last_lint = (
            db.query(KBLintReport)
            .filter(KBLintReport.project_id == p.id)
            .order_by(KBLintReport.created_at.desc())
            .first()
        )
        stamps = [t for t in (last_page, last_source) if t]
        result.append(KBProjectSummary(
            project_id=p.id, project_name=p.name, project_code=p.code,
            pages=pages, sources=sources, indexed_sources=indexed, links=links,
            last_updated=max(stamps) if stamps else None,
            health_score=last_lint.score if last_lint else None,
        ))
    return ResponseModel(code=200, message="success", data=result)


@router.get("/projects/{project_id}/structure", response_model=ResponseModel[Dict[str, Any]])
def project_structure(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Page tree grouped by type — the 'knowledge structure' view."""
    project = _assert_project(db, project_id, current_user)
    pages = sorted(
        _visible_pages(db, project_id, current_user),
        key=lambda p: (p.page_type or "", p.title or ""),
    )
    groups: Dict[str, List[dict]] = {}
    for p in pages:
        groups.setdefault(p.page_type, []).append(_page_brief(p).model_dump())

    special = {
        p.slug: _page_brief(p).model_dump()
        for p in db.query(KBPage).filter(
            KBPage.project_id == project_id, KBPage.slug.in_(_RESERVED)
        ).all()
    }

    return ResponseModel(code=200, message="success", data={
        "project_id": project.id,
        "project_name": project.name,
        "groups": [
            {"type": t, "label": kb_wiki.TYPE_LABELS.get(t, t), "pages": groups.get(t, [])}
            for t in kb_wiki.PAGE_TYPES
        ],
        "special": special,
        "total_pages": len(pages),
    })


@router.get("/projects/{project_id}/graph", response_model=ResponseModel[Dict[str, Any]])
def project_graph(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    pages = _visible_pages(db, project_id, current_user, include_reserved=True)
    visible_ids = {p.id for p in pages}
    links = [
        l for l in db.query(KBLink).filter(KBLink.project_id == project_id).all()
        if l.from_page_id in visible_ids and l.to_page_id in visible_ids
    ]

    inbound: Dict[int, int] = {}
    for l in links:
        inbound[l.to_page_id] = inbound.get(l.to_page_id, 0) + 1

    comm_of = kb_wiki.detect_communities(
        [p.id for p in pages],
        [(l.from_page_id, l.to_page_id) for l in links],
    )

    # Each cluster is named after its most-referenced member.
    buckets: Dict[int, List[KBPage]] = {}
    for p in pages:
        buckets.setdefault(comm_of.get(p.id, 0), []).append(p)

    communities = []
    for cid, members in sorted(buckets.items()):
        hub = max(members, key=lambda m: inbound.get(m.id, 0))
        communities.append({
            "id": cid,
            "label": hub.title,
            "size": len(members),
            "pages": [m.id for m in members],
        })

    return ResponseModel(code=200, message="success", data={
        "nodes": [
            {"id": p.id, "title": p.title, "type": p.page_type,
             "inbound": inbound.get(p.id, 0),
             "community": comm_of.get(p.id, 0),
             "reserved": p.slug in _RESERVED}
            for p in pages
        ],
        "edges": [{"source": l.from_page_id, "target": l.to_page_id} for l in links],
        "communities": communities,
    })


# ─── pages ───────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/pages", response_model=ResponseModel[List[KBPageBrief]])
def list_pages(
    project_id: int,
    page_type: Optional[str] = None,
    keyword: Optional[str] = None,
    include_reserved: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    q = db.query(KBPage).filter(KBPage.project_id == project_id)
    if not include_reserved:
        q = q.filter(KBPage.slug.notin_(_RESERVED))
    if page_type:
        q = q.filter(KBPage.page_type == page_type)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(KBPage.title.ilike(like) | KBPage.content.ilike(like))
    pages = q.order_by(KBPage.updated_at.desc()).limit(300).all()
    pages = [p for p in pages if _can_view_page(p, current_user)]
    return ResponseModel(code=200, message="success", data=[_page_brief(p) for p in pages])


@router.get("/pages/{page_id}", response_model=ResponseModel[KBPageOut])
def get_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.get(KBPage, page_id)
    if not p:
        raise NotFoundException("页面不存在")
    _assert_project(db, p.project_id, current_user)
    if not _can_view_page(p, current_user):
        raise ForbiddenException("该页面已被限制访问")

    inbound = (
        db.query(KBLink, KBPage)
        .join(KBPage, KBPage.id == KBLink.from_page_id)
        .filter(KBLink.to_page_id == page_id)
        .all()
    )
    outbound = (
        db.query(KBLink, KBPage)
        .join(KBPage, KBPage.id == KBLink.to_page_id)
        .filter(KBLink.from_page_id == page_id)
        .all()
    )

    source_ids: List[int] = []
    try:
        source_ids = [int(x) for x in json.loads(p.source_ids or "[]")]
    except Exception:
        source_ids = []

    sources = []
    if source_ids:
        for s in db.query(KBSource).filter(KBSource.id.in_(source_ids)).all():
            sources.append({"id": s.id, "name": s.original_name, "status": s.status})

    return ResponseModel(code=200, message="success", data=KBPageOut(
        id=p.id, project_id=p.project_id, slug=p.slug, title=p.title,
        page_type=p.page_type, summary=p.summary, tags=p.tags, content=p.content,
        source_ids=source_ids, generated_by=p.generated_by,
        visibility=p.visibility or "project", allowed_roles=p.allowed_roles,
        created_by=p.created_by,
        created_at=p.created_at, updated_at=p.updated_at,
        inbound_links=[{"id": page.id, "title": page.title, "page_type": page.page_type} for _, page in inbound],
        outbound_links=[{"id": page.id, "title": page.title, "page_type": page.page_type} for _, page in outbound],
        sources=sources,
    ))


@router.post("/projects/{project_id}/pages", response_model=ResponseModel[KBPageBrief])
def create_page(
    project_id: int,
    payload: KBPageUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    slug = kb_wiki.slugify(payload.title)
    if slug in _RESERVED:
        raise HTTPException(status_code=400, detail="该标题为系统保留")
    if db.query(KBPage).filter(KBPage.project_id == project_id, KBPage.slug == slug).first():
        raise HTTPException(status_code=400, detail="同名页面已存在")

    page = KBPage(
        project_id=project_id, slug=slug, title=payload.title,
        page_type=payload.page_type if payload.page_type in kb_wiki.PAGE_TYPES else "topic",
        summary=payload.summary, content=payload.content, tags=payload.tags,
        visibility=_clean_visibility(payload.visibility),
        allowed_roles=payload.allowed_roles,
        generated_by="manual", created_by=current_user.id,
    )
    db.add(page)
    db.flush()
    kb_wiki.snapshot_page(db, page, "create", user_id=current_user.id)
    kb_wiki.rebuild_links(db, project_id)
    kb_wiki.rebuild_index(db, project_id)
    db.commit()
    db.refresh(page)
    return ResponseModel(code=200, message="页面已创建", data=_page_brief(page))


@router.put("/pages/{page_id}", response_model=ResponseModel[KBPageBrief])
def update_page(
    page_id: int,
    payload: KBPageUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = db.get(KBPage, page_id)
    if not page:
        raise NotFoundException("页面不存在")
    _assert_project(db, page.project_id, current_user)
    if page.slug in _RESERVED:
        raise HTTPException(status_code=400, detail="系统页面不可直接编辑")
    if not _can_edit_page(page, current_user):
        raise ForbiddenException("无权编辑该页面")

    page.title = payload.title or page.title
    page.summary = payload.summary if payload.summary is not None else page.summary
    page.content = payload.content if payload.content is not None else page.content
    page.tags = payload.tags if payload.tags is not None else page.tags
    page.visibility = _clean_visibility(payload.visibility)
    page.allowed_roles = payload.allowed_roles
    if payload.page_type in kb_wiki.PAGE_TYPES:
        page.page_type = payload.page_type
    page.generated_by = "manual"
    page.updated_at = datetime.utcnow()

    db.flush()
    kb_wiki.snapshot_page(db, page, "manual", user_id=current_user.id)
    kb_wiki.rebuild_links(db, page.project_id)
    kb_wiki.rebuild_index(db, page.project_id)
    db.commit()
    db.refresh(page)
    return ResponseModel(code=200, message="页面已更新", data=_page_brief(page))


@router.delete("/pages/{page_id}", response_model=ResponseModel[None])
def delete_page(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = db.get(KBPage, page_id)
    if not page:
        raise NotFoundException("页面不存在")
    _assert_project(db, page.project_id, current_user)
    if page.slug in _RESERVED:
        raise HTTPException(status_code=400, detail="系统页面不可删除")
    if not _can_edit_page(page, current_user):
        raise ForbiddenException("无权删除该页面")

    project_id = page.project_id
    db.delete(page)
    db.flush()
    kb_wiki.rebuild_links(db, project_id)
    kb_wiki.rebuild_index(db, project_id)
    db.commit()
    return ResponseModel(code=200, message="页面已删除")


# ─── page versions ───────────────────────────────────────────────────────────

@router.get("/pages/{page_id}/versions", response_model=ResponseModel[List[KBPageVersionBrief]])
def list_page_versions(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = db.get(KBPage, page_id)
    if not page:
        raise NotFoundException("页面不存在")
    _assert_project(db, page.project_id, current_user)

    rows = (
        db.query(KBPageVersion)
        .filter(KBPageVersion.page_id == page_id)
        .order_by(KBPageVersion.version_no.desc())
        .limit(100)
        .all()
    )
    return ResponseModel(code=200, message="success", data=[
        KBPageVersionBrief(
            id=v.id, page_id=v.page_id, version_no=v.version_no, title=v.title,
            change_type=v.change_type, source_id=v.source_id, created_at=v.created_at,
        ) for v in rows
    ])


@router.get("/versions/{version_id}", response_model=ResponseModel[KBPageVersionOut])
def get_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    v = db.get(KBPageVersion, version_id)
    if not v:
        raise NotFoundException("版本不存在")
    _assert_project(db, v.project_id, current_user)
    return ResponseModel(code=200, message="success", data=KBPageVersionOut(
        id=v.id, page_id=v.page_id, version_no=v.version_no, title=v.title,
        change_type=v.change_type, source_id=v.source_id, created_at=v.created_at,
        summary=v.summary, content=v.content, tags=v.tags, page_type=v.page_type,
    ))


@router.post("/versions/{version_id}/restore", response_model=ResponseModel[KBPageBrief])
def restore_version(
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Roll a page back to an earlier snapshot (the rollback is itself versioned)."""
    v = db.get(KBPageVersion, version_id)
    if not v:
        raise NotFoundException("版本不存在")
    page = db.get(KBPage, v.page_id)
    if not page:
        raise NotFoundException("页面已被删除")
    _assert_project(db, page.project_id, current_user)
    if page.slug in _RESERVED:
        raise HTTPException(status_code=400, detail="系统页面不可回滚")

    page.title = v.title
    page.summary = v.summary
    page.content = v.content
    page.tags = v.tags
    if v.page_type in kb_wiki.PAGE_TYPES:
        page.page_type = v.page_type
    page.generated_by = "manual"
    page.updated_at = datetime.utcnow()

    db.flush()
    kb_wiki.snapshot_page(db, page, "restore", user_id=current_user.id)
    kb_wiki.rebuild_links(db, page.project_id)
    kb_wiki.rebuild_index(db, page.project_id)
    kb_wiki.append_log(
        db, page.project_id,
        f"restore | {page.title}",
        f"回滚到 v{v.version_no}（{v.created_at.strftime('%Y-%m-%d %H:%M')}）",
    )
    db.commit()
    db.refresh(page)
    return ResponseModel(code=200, message=f"已回滚到 v{v.version_no}", data=_page_brief(page))


# ─── sources ─────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/sources", response_model=ResponseModel[List[KBSourceOut]])
def list_sources(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    rows = (
        db.query(KBSource)
        .filter(KBSource.project_id == project_id)
        .order_by(KBSource.created_at.desc())
        .all()
    )
    return ResponseModel(code=200, message="success", data=[_source_out(s) for s in rows])


@router.post("/projects/{project_id}/sources", response_model=ResponseModel[List[KBSourceOut]])
async def upload_sources(
    project_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload files, extract their text immediately, and queue them as sources."""
    _assert_project(db, project_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="未选择文件")

    dest_dir = _kb_root() / str(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.KB_MAX_UPLOAD_MB * 1024 * 1024

    created: List[KBSource] = []
    for f in files:
        name = f.filename or "unnamed"
        if not kb_extract.is_supported(name):
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {name}")

        raw = await f.read()
        if len(raw) > max_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"{name} 超过 {settings.KB_MAX_UPLOAD_MB}MB 限制",
            )

        ext = Path(name).suffix.lower()
        stored = f"{uuid.uuid4().hex}{ext}"
        path = dest_dir / stored
        path.write_bytes(raw)

        text, note = kb_extract.extract_text(path, name)

        src = KBSource(
            project_id=project_id,
            original_name=name[:255],
            stored_name=stored,
            storage_path=str(path),
            mime_type=f.content_type,
            size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            text_content=text or None,
            char_count=len(text),
            extraction_note=note[:500],
            status="ready" if text else "failed",
            error_message=None if text else (note or "未提取到文本")[:2000],
            uploaded_by=current_user.id,
        )
        db.add(src)
        created.append(src)

    db.commit()
    for s in created:
        db.refresh(s)

    return ResponseModel(
        code=200,
        message=f"已上传 {len(created)} 个文件",
        data=[_source_out(s) for s in created],
    )


@router.get("/sources/{source_id}/download")
def download_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.get(KBSource, source_id)
    if not s:
        raise NotFoundException("资料不存在")
    _assert_project(db, s.project_id, current_user)
    path = Path(s.storage_path)
    if not path.exists():
        raise NotFoundException("原始文件已丢失")
    return FileResponse(path, filename=s.original_name, media_type=s.mime_type or "application/octet-stream")


@router.delete("/sources/{source_id}", response_model=ResponseModel[None])
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.get(KBSource, source_id)
    if not s:
        raise NotFoundException("资料不存在")
    _assert_project(db, s.project_id, current_user)

    project_id = s.project_id
    path = Path(s.storage_path)
    db.delete(s)
    db.flush()
    kb_wiki.rebuild_index(db, project_id)
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except Exception:
        logger.warning("failed to remove file %s", path)
    return ResponseModel(code=200, message="资料已删除")


@router.post("/sources/{source_id}/ingest", response_model=ResponseModel[Dict[str, Any]])
def ingest_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Push the source onto the Redis ingest queue.

    Poll /projects/{pid}/jobs (or /jobs/status) to follow progress. Queued work
    survives API restarts, unlike FastAPI BackgroundTasks.
    """
    s = db.get(KBSource, source_id)
    if not s:
        raise NotFoundException("资料不存在")
    _assert_project(db, s.project_id, current_user)
    if not s.text_content:
        raise HTTPException(status_code=400, detail="该资料没有可用的文本内容，无法摄入")
    if s.status in ("ingesting", "queued"):
        raise HTTPException(status_code=409, detail="该资料已在队列中或正在摄入")

    try:
        job = kb_queue.enqueue_ingest(db, s, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ResponseModel(
        code=200,
        message="已加入摄入队列",
        data={
            "source_id": source_id,
            "status": "queued",
            "job_id": job.id,
            "queue_depth": kb_queue.queue_depth(),
        },
    )


@router.get("/projects/{project_id}/jobs", response_model=ResponseModel[List[KBIngestJobOut]])
def list_jobs(
    project_id: int,
    source_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    q = db.query(KBIngestJob).filter(KBIngestJob.project_id == project_id)
    if source_id:
        q = q.filter(KBIngestJob.source_id == source_id)
    rows = q.order_by(KBIngestJob.created_at.desc()).limit(limit).all()
    return ResponseModel(code=200, message="success", data=[
        KBIngestJobOut(
            id=j.id, project_id=j.project_id, source_id=j.source_id,
            status=j.status, stage=j.stage, progress=j.progress or 0,
            message=j.message, pages_created=j.pages_created or 0,
            pages_updated=j.pages_updated or 0, used_llm=j.used_llm,
            started_at=j.started_at, finished_at=j.finished_at, created_at=j.created_at,
        ) for j in rows
    ])


@router.get("/queue/status", response_model=ResponseModel[Dict[str, Any]])
def queue_status(
    current_user: User = Depends(get_current_user),
):
    """Current depth of the ingest queue (pending items)."""
    return ResponseModel(code=200, message="success", data={
        "depth": kb_queue.queue_depth(),
        "workers": settings.KB_INGEST_WORKERS,
    })


# ─── notifications ───────────────────────────────────────────────────────────

@router.get("/notify/status", response_model=ResponseModel[Dict[str, Any]])
def notify_status(
    current_user: User = Depends(get_current_user),
):
    from app.services import notifier

    return ResponseModel(code=200, message="success", data={
        "enabled": settings.KB_NOTIFY_ENABLED,
        "configured": notifier.is_email_configured(),
        "email": current_user.email,
        "smtp_host": settings.SMTP_HOST or None,
        "smtp_port": settings.SMTP_PORT,
        "from": settings.SMTP_FROM or settings.SMTP_USER or None,
        "on_ingest": settings.KB_NOTIFY_ON_INGEST,
        "lint_threshold": settings.KB_NOTIFY_LINT_SCORE_BELOW,
    })


@router.get("/notify/prefs", response_model=ResponseModel[KBNotifyPrefOut])
def get_notify_prefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current user's subscription. A missing row means "everything on"."""
    pref = db.query(KBNotifyPref).filter(KBNotifyPref.user_id == current_user.id).first()
    if pref is None:
        return ResponseModel(code=200, message="success", data=KBNotifyPrefOut(
            enabled=True, on_ingest=True, on_lint=True, email=current_user.email,
        ))
    return ResponseModel(code=200, message="success", data=KBNotifyPrefOut(
        enabled=bool(pref.enabled), on_ingest=bool(pref.on_ingest),
        on_lint=bool(pref.on_lint), email=current_user.email,
    ))


@router.put("/notify/prefs", response_model=ResponseModel[KBNotifyPrefOut])
def update_notify_prefs(
    payload: KBNotifyPrefIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = db.query(KBNotifyPref).filter(KBNotifyPref.user_id == current_user.id).first()
    if pref is None:
        pref = KBNotifyPref(user_id=current_user.id)
        db.add(pref)
    pref.enabled = payload.enabled
    pref.on_ingest = payload.on_ingest
    pref.on_lint = payload.on_lint
    db.commit()
    db.refresh(pref)
    return ResponseModel(code=200, message="已保存", data=KBNotifyPrefOut(
        enabled=bool(pref.enabled), on_ingest=bool(pref.on_ingest),
        on_lint=bool(pref.on_lint), email=current_user.email,
    ))


@router.post("/notify/test", response_model=ResponseModel[Dict[str, Any]])
async def notify_test(
    current_user: User = Depends(get_current_user),
):
    """Send a test email to the current user so SMTP can be verified."""
    from app.services import notifier

    if not _is_admin(current_user):
        raise ForbiddenException("仅管理员可发送测试邮件")
    if not current_user.email:
        raise HTTPException(status_code=400, detail="当前账号未配置邮箱")

    subject = "[AIPM] 知识库通知测试"
    body = notifier._wrap(subject, [
        ("收件人", current_user.email),
        ("SMTP", f"{settings.SMTP_HOST}:{settings.SMTP_PORT}"),
        ("说明", "收到这封邮件说明邮件通知配置正常"),
    ])
    sent = await notifier.send_email([current_user.email], subject, body)
    if not sent:
        raise HTTPException(
            status_code=400,
            detail="发送失败，请检查 SMTP 配置或查看后端日志",
        )
    return ResponseModel(code=200, message="测试邮件已发送", data={"to": current_user.email})


# ─── lint (体检) ─────────────────────────────────────────────────────────────

def _lint_out(r: KBLintReport) -> KBLintOut:
    try:
        issues = json.loads(r.issues_json or "[]")
    except Exception:
        issues = []
    try:
        stats = json.loads(r.stats_json or "{}")
    except Exception:
        stats = {}
    return KBLintOut(
        id=r.id, project_id=r.project_id, score=r.score,
        issues=issues, stats=stats, created_at=r.created_at,
    )


@router.post("/projects/{project_id}/lint", response_model=ResponseModel[KBLintOut])
async def run_lint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _assert_project(db, project_id, current_user)
    report = await kb_wiki.lint_project(db, project, current_user.id)
    return ResponseModel(code=200, message="体检完成", data=_lint_out(report))


@router.get("/projects/{project_id}/lint/latest", response_model=ResponseModel[Optional[KBLintOut]])
def latest_lint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_project(db, project_id, current_user)
    r = (
        db.query(KBLintReport)
        .filter(KBLintReport.project_id == project_id)
        .order_by(KBLintReport.created_at.desc())
        .first()
    )
    return ResponseModel(code=200, message="success", data=_lint_out(r) if r else None)


def _accessible_projects(db: Session, user: User) -> List[Project]:
    if _is_admin(user):
        return db.query(Project).order_by(Project.updated_at.desc()).all()
    ids = PermissionScopedTools.get_user_accessible_project_ids(user, db)
    return db.query(Project).filter(Project.id.in_(ids)).all() if ids else []


def _sse(agen):
    """Wrap an event async-generator into SSE frames."""
    async def _gen():
        async for ev in agen:
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
    return _gen()


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


# ─── Q&A over the wiki ───────────────────────────────────────────────────────

@router.post("/projects/{project_id}/ask", response_model=ResponseModel[KBAskResponse])
async def ask_knowledge_base(
    project_id: int,
    payload: KBAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Answer a question from wiki pages, optionally filing the answer back."""
    project = _assert_project(db, project_id, current_user)
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    result = await kb_wiki.answer_question(
        db, [project], question, current_user.id,
        page_filter=lambda p: _can_view_page(p, current_user),
    )

    saved_id = saved_title = None
    if payload.save_as_page and result.get("answer"):
        base_title = f"问答：{question[:40]}"
        slug = kb_wiki.slugify(base_title)
        suffix = 2
        while db.query(KBPage).filter(
            KBPage.project_id == project_id, KBPage.slug == slug
        ).first():
            slug = kb_wiki.slugify(f"{base_title}-{suffix}")
            suffix += 1
            if suffix > 50:
                break

        ptype = payload.page_type if payload.page_type in kb_wiki.PAGE_TYPES else "topic"
        refs = "\n".join(f"- [[{c['title']}]]" for c in result.get("citations", []))
        page = KBPage(
            project_id=project_id,
            slug=slug,
            title=base_title[:255],
            page_type=ptype,
            summary=question[:500],
            content=result["answer"] + (f"\n\n## 参考页面\n{refs}" if refs else ""),
            tags="问答",
            generated_by="manual",
            created_by=current_user.id,
        )
        db.add(page)
        db.flush()
        kb_wiki.snapshot_page(db, page, "create", user_id=current_user.id)
        kb_wiki.rebuild_links(db, project_id)
        kb_wiki.rebuild_index(db, project_id)
        kb_wiki.append_log(
            db, project_id, f"query | {question[:60]}",
            "问答结果已归档为知识库页面",
        )
        db.commit()
        db.refresh(page)
        saved_id, saved_title = page.id, page.title

    return ResponseModel(code=200, message="success", data=KBAskResponse(
        answer=result["answer"],
        citations=[KBAskCitation(**c) for c in result.get("citations", [])],
        used_llm=result.get("used_llm", False),
        saved_page_id=saved_id,
        saved_page_title=saved_title,
    ))


@router.post("/projects/{project_id}/ask/stream")
async def ask_knowledge_base_stream(
    project_id: int,
    payload: KBAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streamed version of /ask — same retrieval, token-by-token answer."""
    project = _assert_project(db, project_id, current_user)
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    return StreamingResponse(
        _sse(kb_wiki.stream_answer(
            db, [project], question, current_user.id,
            page_filter=lambda p: _can_view_page(p, current_user),
        )),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ─── cross-project knowledge base ────────────────────────────────────────────

@router.post("/ask", response_model=ResponseModel[KBAskResponse])
async def ask_all_projects(
    payload: KBAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask across every project the user can access."""
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    projects = _accessible_projects(db, current_user)
    if not projects:
        raise HTTPException(status_code=400, detail="没有可访问的项目")

    result = await kb_wiki.answer_question(
        db, projects, question, current_user.id,
        page_filter=lambda p: _can_view_page(p, current_user),
    )
    return ResponseModel(code=200, message="success", data=KBAskResponse(
        answer=result["answer"],
        citations=[KBAskCitation(**c) for c in result.get("citations", [])],
        used_llm=result.get("used_llm", False),
    ))


@router.post("/ask/stream")
async def ask_all_projects_stream(
    payload: KBAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    projects = _accessible_projects(db, current_user)
    if not projects:
        raise HTTPException(status_code=400, detail="没有可访问的项目")

    return StreamingResponse(
        _sse(kb_wiki.stream_answer(
            db, projects, question, current_user.id,
            page_filter=lambda p: _can_view_page(p, current_user),
        )),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/structure/all", response_model=ResponseModel[Dict[str, Any]])
def structure_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merged knowledge structure across all accessible projects."""
    projects = _accessible_projects(db, current_user)
    groups: Dict[str, List[dict]] = {}
    total = 0

    for proj in projects:
        pages = sorted(
            _visible_pages(db, proj.id, current_user),
            key=lambda p: p.title or "",
        )
        for page in pages:
            item = _page_brief(page).model_dump()
            item["project_id"] = proj.id
            item["project_name"] = proj.name
            groups.setdefault(page.page_type, []).append(item)
            total += 1

    return ResponseModel(code=200, message="success", data={
        "project_id": 0,
        "project_name": "全部项目",
        "groups": [
            {"type": t, "label": kb_wiki.TYPE_LABELS.get(t, t), "pages": groups.get(t, [])}
            for t in kb_wiki.PAGE_TYPES
        ],
        "special": {},
        "total_pages": total,
    })


@router.get("/graph/all", response_model=ResponseModel[Dict[str, Any]])
def graph_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Merged graph across projects; communities are detected globally."""
    projects = _accessible_projects(db, current_user)
    proj_names = {p.id: p.name for p in projects}

    pages: List[KBPage] = []
    links: List[KBLink] = []
    for proj in projects:
        pages.extend(_visible_pages(db, proj.id, current_user, include_reserved=True))
    visible_ids = {p.id for p in pages}
    for proj in projects:
        links.extend(
            l for l in db.query(KBLink).filter(KBLink.project_id == proj.id).all()
            if l.from_page_id in visible_ids and l.to_page_id in visible_ids
        )

    inbound: Dict[int, int] = {}
    for l in links:
        inbound[l.to_page_id] = inbound.get(l.to_page_id, 0) + 1

    comm_of = kb_wiki.detect_communities(
        [p.id for p in pages], [(l.from_page_id, l.to_page_id) for l in links]
    )

    buckets: Dict[int, List[KBPage]] = {}
    for p in pages:
        buckets.setdefault(comm_of.get(p.id, 0), []).append(p)

    communities = []
    for cid, members in sorted(buckets.items()):
        hub = max(members, key=lambda m: inbound.get(m.id, 0))
        communities.append({
            "id": cid, "label": hub.title, "size": len(members),
            "pages": [m.id for m in members],
        })

    return ResponseModel(code=200, message="success", data={
        "nodes": [
            {"id": p.id, "title": p.title, "type": p.page_type,
             "inbound": inbound.get(p.id, 0),
             "community": comm_of.get(p.id, 0),
             "project_id": p.project_id,
             "project_name": proj_names.get(p.project_id, ""),
             "reserved": p.slug in _RESERVED}
            for p in pages
        ],
        "edges": [{"source": l.from_page_id, "target": l.to_page_id} for l in links],
        "communities": communities,
    })


@router.post("/lint/all", response_model=ResponseModel[List[Dict[str, Any]]])
async def lint_all_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Health-check every accessible project (manual trigger for the scheduler)."""
    if not _is_admin(current_user):
        raise ForbiddenException("仅管理员可执行全量体检")

    results: List[Dict[str, Any]] = []
    for proj in _accessible_projects(db, current_user):
        page_count = db.query(func.count(KBPage.id)).filter(
            KBPage.project_id == proj.id, KBPage.slug.notin_(_RESERVED)
        ).scalar() or 0
        if page_count == 0:
            continue
        report = await kb_wiki.lint_project(db, proj, current_user.id)
        try:
            issue_count = len(json.loads(report.issues_json or "[]"))
        except Exception:
            issue_count = 0
        results.append({
            "project_id": proj.id, "project_name": proj.name,
            "score": report.score, "issues": issue_count,
        })

    return ResponseModel(
        code=200,
        message=f"已完成 {len(results)} 个项目的体检",
        data=results,
    )


# ─── export ──────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/export")
def export_wiki(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the whole wiki as a zip of markdown files."""
    project = _assert_project(db, project_id, current_user)
    pages = sorted(
        _visible_pages(db, project_id, current_user, include_reserved=True),
        key=lambda p: p.page_type or "",
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in pages:
            folder = "raw-index" if p.slug in _RESERVED else p.page_type
            front = (
                f"---\ntitle: {p.title}\ntype: {p.page_type}\n"
                f"updated: {p.updated_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"tags: {p.tags or ''}\n---\n\n"
            )
            zf.writestr(f"{folder}/{p.slug}.md", front + (p.content or ""))
        zf.writestr(
            "README.md",
            f"# {project.name} 知识库导出\n\n"
            f"- 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- 页面数量：{len(pages)}\n\n"
            f"目录结构按页面类型分组，可直接用 Obsidian 打开。\n",
        )
    buf.seek(0)

    filename = f"{project.code or project.id}-wiki-{datetime.now().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
