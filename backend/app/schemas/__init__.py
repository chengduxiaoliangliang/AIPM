from app.schemas.common import ResponseModel, PaginatedData, PageParams
from app.schemas.auth import LoginRequest, Token, TokenPayload, UserInfoResponse
from app.schemas.user import (
    DepartmentCreate, DepartmentUpdate, DepartmentOut,
    RoleCreate, RoleUpdate, RoleOut,
    UserCreate, UserUpdate, UserOut, PasswordChangeRequest
)
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectDetailOut,
    ProjectMemberCreate, ProjectMemberOut,
    MilestoneCreate, MilestoneUpdate, MilestoneOut
)
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskStatusUpdate, TaskOut, TaskDetailOut,
    SubTaskCreate, SubTaskUpdate, SubTaskOut,
    TaskCommentCreate, TaskCommentOut
)
from app.schemas.worklog import WorkLogCreate, WorkLogApproval, WorkLogOut
from app.schemas.issue import IssueCreate, IssueUpdate, IssueOut
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentOut
from app.schemas.stats import DashboardStats, DashboardMetrics
