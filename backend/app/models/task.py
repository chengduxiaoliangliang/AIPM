from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Task(Base):
    __tablename__ = "pm_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    milestone_id = Column(Integer, ForeignKey("pm_milestones.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    task_type = Column(String(32), default="task")      # 'task', 'feature', 'bug', 'improvement', 'research'
    status = Column(String(32), default="todo")         # 'todo', 'in_progress', 'in_review', 'testing', 'done'
    priority = Column(String(32), default="medium")     # 'low', 'medium', 'high', 'urgent'
    creator_id = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    estimated_hours = Column(Float, default=0.0)
    actual_hours = Column(Float, default=0.0)
    progress = Column(Integer, default=0)               # 0 - 100
    start_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    order_num = Column(Integer, default=0)              # Order within Kanban column
    tags = Column(String(255), nullable=True)           # Comma-separated tags, e.g. "Frontend,UI,Auth"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="tasks")
    creator = relationship("User", foreign_keys=[creator_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    milestone = relationship("Milestone")
    subtasks = relationship("SubTask", back_populates="task", cascade="all, delete-orphan")
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    worklogs = relationship("WorkLog", back_populates="task", cascade="all, delete-orphan")

class SubTask(Base):
    __tablename__ = "pm_subtasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("pm_tasks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    is_completed = Column(Boolean, default=False)
    assignee_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="subtasks")
    assignee = relationship("User")

class TaskComment(Base):
    __tablename__ = "pm_task_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("pm_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    user = relationship("User")
