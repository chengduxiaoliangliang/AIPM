from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class IssueBase(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    priority: str = "medium"
    status: str = "open"
    assignee_id: Optional[int] = None

class IssueCreate(IssueBase):
    pass

class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[int] = None
    resolution: Optional[str] = None

class IssueOut(IssueBase):
    id: int
    reporter_id: int
    reporter_name: Optional[str] = None
    assignee_name: Optional[str] = None
    project_name: Optional[str] = None
    task_title: Optional[str] = None
    resolution: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
