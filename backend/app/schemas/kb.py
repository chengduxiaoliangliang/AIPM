from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class KBPageBrief(BaseModel):
    id: int
    slug: str
    title: str
    page_type: str
    summary: Optional[str] = None
    tags: Optional[str] = None
    updated_at: datetime


class KBPageOut(KBPageBrief):
    project_id: int
    content: Optional[str] = None
    source_ids: Optional[List[int]] = None
    generated_by: Optional[str] = None
    created_at: datetime
    inbound_links: List[Dict[str, Any]] = []
    outbound_links: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []


class KBPageUpsert(BaseModel):
    title: str
    page_type: str = "topic"
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None


class KBSourceOut(BaseModel):
    id: int
    project_id: int
    original_name: str
    mime_type: Optional[str] = None
    size_bytes: int = 0
    char_count: int = 0
    status: str
    extraction_note: Optional[str] = None
    error_message: Optional[str] = None
    uploaded_by: Optional[int] = None
    created_at: datetime


class KBIngestJobOut(BaseModel):
    id: int
    project_id: int
    source_id: Optional[int] = None
    status: str
    stage: str
    progress: int
    message: Optional[str] = None
    pages_created: int = 0
    pages_updated: int = 0
    used_llm: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class KBLintIssue(BaseModel):
    type: str
    severity: str = "low"
    page: Optional[str] = None
    detail: str
    suggestion: Optional[str] = None
    source: Optional[str] = None


class KBLintOut(BaseModel):
    id: int
    project_id: int
    score: int
    issues: List[KBLintIssue] = []
    stats: Dict[str, Any] = {}
    created_at: datetime


class KBProjectSummary(BaseModel):
    project_id: int
    project_name: str
    project_code: Optional[str] = None
    pages: int = 0
    sources: int = 0
    indexed_sources: int = 0
    links: int = 0
    last_updated: Optional[datetime] = None
    health_score: Optional[int] = None


class KBPageVersionBrief(BaseModel):
    id: int
    page_id: int
    version_no: int
    title: str
    change_type: str
    source_id: Optional[int] = None
    created_at: datetime


class KBPageVersionOut(KBPageVersionBrief):
    summary: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    page_type: Optional[str] = None


class KBAskRequest(BaseModel):
    question: str
    save_as_page: bool = False
    page_type: str = "topic"


class KBAskCitation(BaseModel):
    id: int
    title: str
    page_type: str
    project: Optional[str] = None


class KBAskResponse(BaseModel):
    answer: str
    citations: List[KBAskCitation] = []
    used_llm: bool = False
    saved_page_id: Optional[int] = None
    saved_page_title: Optional[str] = None
