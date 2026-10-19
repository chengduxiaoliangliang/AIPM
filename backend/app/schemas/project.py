from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel

# Project Member Schemas
class ProjectMemberBase(BaseModel):
    user_id: int
    project_role: str = "developer"

class ProjectMemberCreate(ProjectMemberBase):
    pass

class ProjectMemberOut(ProjectMemberBase):
    id: int
    project_id: int
    username: str
    nickname: str
    avatar: Optional[str] = None
    position: Optional[str] = None
    joined_at: datetime

    class Config:
        from_attributes = True

# Milestone Schemas
class MilestoneBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: date
    status: str = "pending"
    order_num: int = 0

class MilestoneCreate(MilestoneBase):
    pass

class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    order_num: Optional[int] = None

class MilestoneOut(MilestoneBase):
    id: int
    project_id: int
    reached_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Project Schemas
class ProjectBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    owner_id: int
    status: str = "in_progress"
    priority: str = "medium"
    budget: float = 0.0
    progress: int = 0
    health: str = "good"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    cover_image: Optional[str] = None

class ProjectCreate(ProjectBase):
    member_user_ids: List[int] = []

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    budget: Optional[float] = None
    consumed_budget: Optional[float] = None
    progress: Optional[int] = None
    health: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    cover_image: Optional[str] = None

class ProjectOut(ProjectBase):
    id: int
    consumed_budget: float
    owner_name: Optional[str] = None
    owner_avatar: Optional[str] = None
    member_count: int = 0
    task_count: int = 0
    completed_task_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProjectDetailOut(ProjectOut):
    members: List[ProjectMemberOut] = []
    milestones: List[MilestoneOut] = []
