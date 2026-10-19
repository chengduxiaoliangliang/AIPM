from typing import List, Dict, Any
from pydantic import BaseModel

class DashboardMetrics(BaseModel):
    total_projects: int
    active_projects: int
    total_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    pending_approvals: int
    total_hours: float
    total_issues: int
    open_issues: int

class StatusCount(BaseModel):
    status: str
    count: int
    name: str

class PriorityCount(BaseModel):
    priority: str
    count: int
    name: str

class MonthlyTrend(BaseModel):
    month: str
    created_tasks: int
    completed_tasks: int
    logged_hours: float

class MemberWorkload(BaseModel):
    user_id: int
    name: str
    avatar: str
    task_count: int
    logged_hours: float
    completion_rate: float

class DashboardStats(BaseModel):
    metrics: DashboardMetrics
    project_status_dist: List[StatusCount]
    task_priority_dist: List[PriorityCount]
    monthly_trends: List[MonthlyTrend]
    member_workloads: List[MemberWorkload]
    recent_activities: List[Dict[str, Any]]
