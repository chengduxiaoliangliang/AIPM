"""
LLM Wiki knowledge base models.

Three layers, mirroring the llm-wiki pattern:
  raw sources  -> KBSource   (immutable uploaded files + extracted text)
  the wiki     -> KBPage     (LLM-maintained markdown pages)
  links        -> KBLink     (resolved [[wiki links]] between pages)

Supporting tables:
  KBIngestJob     ingest pipeline progress (upload -> extract -> analyse -> write)
  KBLintReport    periodic health-check results
"""
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT

from app.database import Base

# LONGTEXT on MySQL (file bodies can exceed the 64 KB TEXT limit), TEXT elsewhere.
LongText = Text().with_variant(LONGTEXT, "mysql")


class KBSource(Base):
    """An immutable raw source document uploaded into a project's knowledge base."""

    __tablename__ = "pm_kb_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False, index=True)

    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=True)
    size_bytes = Column(Integer, default=0)
    sha256 = Column(String(64), nullable=True, index=True)

    # Extracted plain text — the only thing the LLM ever reads.
    text_content = Column(LongText, nullable=True)
    char_count = Column(Integer, default=0)
    extraction_note = Column(String(512), nullable=True)

    # uploaded | ready | ingesting | indexed | failed
    status = Column(String(32), default="uploaded", index=True)
    error_message = Column(Text, nullable=True)

    uploaded_by = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KBPage(Base):
    """A wiki page owned and maintained by the LLM."""

    __tablename__ = "pm_kb_pages"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_kb_page_project_slug"),
        Index("ix_kb_page_project_type", "project_id", "page_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False, index=True)

    slug = Column(String(160), nullable=False)
    title = Column(String(255), nullable=False)
    # overview | topic | entity | source | comparison | decision | log | index
    page_type = Column(String(32), default="topic", index=True)
    summary = Column(Text, nullable=True)
    content = Column(LongText, nullable=True)
    tags = Column(String(255), nullable=True)          # comma separated
    source_ids = Column(Text, nullable=True)           # JSON array of KBSource ids

    # draft | published
    status = Column(String(16), default="published")
    generated_by = Column(String(32), default="llm")   # llm | manual
    created_by = Column(Integer, ForeignKey("sys_users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KBLink(Base):
    """Resolved outgoing [[wiki link]] from one page to another."""

    __tablename__ = "pm_kb_links"
    __table_args__ = (
        Index("ix_kb_link_from", "from_page_id"),
        Index("ix_kb_link_to", "to_page_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    from_page_id = Column(Integer, ForeignKey("pm_kb_pages.id", ondelete="CASCADE"), nullable=False)
    to_page_id = Column(Integer, ForeignKey("pm_kb_pages.id", ondelete="CASCADE"), nullable=False)
    raw_text = Column(String(255), nullable=True)


class KBIngestJob(Base):
    """Progress record for one ingest run."""

    __tablename__ = "pm_kb_ingest_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("pm_kb_sources.id", ondelete="CASCADE"), nullable=True, index=True)

    # queued | running | succeeded | failed
    status = Column(String(16), default="queued", index=True)
    # extracting | analysing | writing | done
    stage = Column(String(32), default="queued")
    progress = Column(Integer, default=0)
    message = Column(Text, nullable=True)

    pages_created = Column(Integer, default=0)
    pages_updated = Column(Integer, default=0)
    used_llm = Column(String(8), default="false")

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class KBLintReport(Base):
    """Result of a health-check pass over a project's wiki."""

    __tablename__ = "pm_kb_lint_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False, index=True)

    score = Column(Integer, default=100)
    issues_json = Column(LongText, nullable=True)   # JSON array
    stats_json = Column(LongText, nullable=True)    # JSON object
    created_by = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
