from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Document(Base):
    __tablename__ = "pm_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(64), default="general")  # 'requirement', 'design', 'api', 'deployment', 'meeting', 'general'
    content = Column(Text, nullable=True)             # Markdown / Rich text
    version = Column(String(32), default="v1.0")
    file_url = Column(String(512), nullable=True)     # Attachment URL
    author_id = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="documents")
    author = relationship("User")
