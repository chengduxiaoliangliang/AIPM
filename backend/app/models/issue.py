from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.task import Task

class Issue(Base):
    __tablename__ = "pm_issues"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("pm_tasks.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(32), default="medium")  # 'fatal', 'critical', 'medium', 'low'
    priority = Column(String(32), default="medium")  # 'urgent', 'high', 'medium', 'low'
    status = Column(String(32), default="open")      # 'open', 'in_progress', 'resolved', 'closed', 'rejected'
    reporter_id = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    resolution = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="issues")
    reporter = relationship("User", foreign_keys=[reporter_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    task = relationship("Task")
