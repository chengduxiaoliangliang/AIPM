from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Project(Base):
    __tablename__ = "pm_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)  # e.g., 'AIPM-2026'
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("sys_users.id"), nullable=False)
    status = Column(String(32), default="in_progress")  # 'planning', 'in_progress', 'testing', 'completed', 'suspended'
    priority = Column(String(32), default="medium")     # 'low', 'medium', 'high', 'urgent'
    budget = Column(Float, default=0.0)                 # Budget amount (RMB/USD)
    consumed_budget = Column(Float, default=0.0)        # Consumed budget
    progress = Column(Integer, default=0)               # 0 - 100 percentage
    health = Column(String(32), default="good")         # 'good', 'warning', 'danger'
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    cover_image = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")

class ProjectMember(Base):
    __tablename__ = "pm_project_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("sys_users.id", ondelete="CASCADE"), nullable=False)
    project_role = Column(String(64), default="developer")  # 'pm', 'tech_lead', 'developer', 'qa', 'designer', 'viewer'
    joined_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="members")
    user = relationship("User")

class Milestone(Base):
    __tablename__ = "pm_milestones"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("pm_projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=False)
    status = Column(String(32), default="pending")  # 'pending', 'in_progress', 'reached', 'delayed'
    order_num = Column(Integer, default=0)
    reached_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="milestones")
