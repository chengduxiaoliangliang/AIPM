from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class WorkLog(Base):
    __tablename__ = "pm_worklogs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("pm_tasks.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("sys_users.id", ondelete="CASCADE"), nullable=False)
    log_date = Column(Date, nullable=False)
    hours = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(32), default="pending")  # 'pending', 'approved', 'rejected'
    approver_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    approval_remark = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project")
    task = relationship("Task", back_populates="worklogs")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approver_id])
