from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.roles import router as roles_router
from app.api.v1.depts import router as depts_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.worklogs import router as worklogs_router
from app.api.v1.issues import router as issues_router
from app.api.v1.documents import router as documents_router
from app.api.v1.kb import router as kb_router
from app.api.v1.stats import router as stats_router
from app.api.v1.logs import router as logs_router
from app.api.v1.ai import router as ai_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证授权"])
api_router.include_router(users_router, prefix="/users", tags=["用户管理"])
api_router.include_router(roles_router, prefix="/roles", tags=["角色权限"])
api_router.include_router(depts_router, prefix="/depts", tags=["部门管理"])
api_router.include_router(projects_router, prefix="/projects", tags=["项目管理"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["任务协作"])
api_router.include_router(worklogs_router, prefix="/worklogs", tags=["工时管理"])
api_router.include_router(issues_router, prefix="/issues", tags=["缺陷跟踪"])
api_router.include_router(documents_router, prefix="/documents", tags=["知识库文档"])
api_router.include_router(kb_router, prefix="/kb", tags=["知识库(LLM Wiki)"])
api_router.include_router(stats_router, prefix="/stats", tags=["统计大盘"])
api_router.include_router(logs_router, prefix="/logs", tags=["审计日志"])
api_router.include_router(ai_router, prefix="/ai", tags=["AI智能小精灵"])

