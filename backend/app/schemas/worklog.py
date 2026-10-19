from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel

class WorkLogBase(BaseModel):
    project_id: int
    task_id: Optional[int] = None
    log_date: date
    hours: float
    description: str

class WorkLogCreate(WorkLogBase):
    pass

class WorkLogApproval(BaseModel):
    status: str  # 'approved' or 'rejected'
    approval_remark: Optional[str] = None

class WorkLogOut(WorkLogBase):
    id: int
    user_id: int
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None
    project_name: Optional[str] = None
    task_title: Optional[str] = None
    status: str
    approver_id: Optional[int] = None
    approver_name: Optional[str] = None
    approval_remark: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
