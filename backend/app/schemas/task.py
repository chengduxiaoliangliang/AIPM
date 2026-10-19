from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel

# Subtask Schemas
class SubTaskBase(BaseModel):
    title: str
    is_completed: bool = False
    assignee_id: Optional[int] = None

class SubTaskCreate(SubTaskBase):
    pass

class SubTaskUpdate(BaseModel):
    title: Optional[str] = None
    is_completed: Optional[bool] = None
    assignee_id: Optional[int] = None

class SubTaskOut(SubTaskBase):
    id: int
    task_id: int
    assignee_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Comment Schemas
class TaskCommentCreate(BaseModel):
    content: str

class TaskCommentOut(BaseModel):
    id: int
    task_id: int
    user_id: int
    username: str
    user_nickname: str
    user_avatar: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

# Task Schemas
class TaskBase(BaseModel):
    project_id: int
    milestone_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    task_type: str = "task"
    status: str = "todo"
    priority: str = "medium"
    assignee_id: Optional[int] = None
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    progress: int = 0
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    order_num: int = 0
    tags: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    milestone_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    progress: Optional[int] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    order_num: Optional[int] = None
    tags: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: str
    order_num: Optional[int] = None

class TaskOut(TaskBase):
    id: int
    creator_id: int
    creator_name: Optional[str] = None
    assignee_name: Optional[str] = None
    assignee_avatar: Optional[str] = None
    project_name: Optional[str] = None
    milestone_title: Optional[str] = None
    subtask_count: int = 0
    completed_subtask_count: int = 0
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskDetailOut(TaskOut):
    subtasks: List[SubTaskOut] = []
    comments: List[TaskCommentOut] = []
