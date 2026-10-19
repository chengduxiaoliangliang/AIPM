"""
Permission-Scoped Tools for AIPM LangChain Agent.

Every tool method enforces RBAC data isolation:
- Accepts current_user + db session
- Returns formatted Markdown string (never raises exceptions to caller)
- Logs warnings on internal errors instead of propagating them
"""
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.project import Project, ProjectMember, Milestone
from app.models.task import Task, SubTask
from app.models.worklog import WorkLog
from app.models.issue import Issue
from app.models.document import Document

logger = logging.getLogger(__name__)


def _timed(fn_name: str):
    """Decorator-style context manager for tool execution timing logging."""
    class _Timer:
        def __enter__(self):
            self._start = time.perf_counter()
            return self
        def __exit__(self, *args):
            elapsed = (time.perf_counter() - self._start) * 1000
            logger.debug(f"[Tool:{fn_name}] executed in {elapsed:.1f}ms")
    return _Timer()


class PermissionScopedTools:
    """
    RBAC-enforced Tools for LangChain AIPM Agent.
    All methods return safe Markdown strings — never raise to callers.
    """

    @staticmethod
    def get_user_accessible_project_ids(user: User, db: Session) -> List[int]:
        """Get list of project IDs the user has permission to view."""
        try:
            if user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in user.roles):
                return [p.id for p in db.query(Project.id).all()]

            member_pids = [
                m.project_id
                for m in db.query(ProjectMember.project_id)
                .filter(ProjectMember.user_id == user.id).all()
            ]
            owner_pids = [
                p.id
                for p in db.query(Project.id)
                .filter((Project.owner_id == user.id) | (Project.created_by == user.id)).all()
            ]
            return list(set(member_pids + owner_pids))
        except Exception as e:
            logger.warning(f"get_user_accessible_project_ids failed: {e}")
            return []

    @classmethod
    def query_projects(
        cls, user: User, db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None
    ) -> str:
        """Query projects accessible to the current user."""
        with _timed("query_projects"):
            try:
                accessible_ids = cls.get_user_accessible_project_ids(user, db)
                if not accessible_ids:
                    return "【检索结果】您当前未参与任何项目。"

                query = db.query(Project).filter(Project.id.in_(accessible_ids))
                if keyword:
                    query = query.filter(
                        (Project.name.ilike(f"%{keyword}%")) | (Project.code.ilike(f"%{keyword}%"))
                    )
                if status:
                    query = query.filter(Project.status == status)

                projects = query.limit(10).all()
                if not projects:
                    return "【检索结果】未找到符合条件的项目。"

                res = [f"【您可访问的项目列表（共 {len(projects)} 个）】:"]
                for p in projects:
                    owner_name = p.owner.nickname if p.owner else "未指定"
                    res.append(
                        f"- [ID:{p.id}] {p.name} ({p.code}) | 状态: {p.status} | 进度: {p.progress}% | "
                        f"负责人: {owner_name} | 预算: ¥{p.budget or 0:,.2f} | 截止日期: {p.end_date or '未设定'}"
                    )
                return "\n".join(res)
            except Exception as e:
                logger.warning(f"query_projects tool error: {e}")
                return "【系统提示】项目查询暂时不可用，请稍后重试。"

    @classmethod
    def query_tasks(
        cls, user: User, db: Session,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        my_tasks_only: bool = False
    ) -> str:
        """Query tasks within the user's permission scope."""
        with _timed("query_tasks"):
            try:
                accessible_pids = cls.get_user_accessible_project_ids(user, db)
                query = db.query(Task).filter(Task.project_id.in_(accessible_pids))

                is_admin = user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in user.roles)
                if my_tasks_only or not is_admin:
                    query = query.filter(Task.assignee_id == user.id)

                if project_id:
                    if project_id not in accessible_pids:
                        return "【权限拦截】您无权访问该项目的任务数据。"
                    query = query.filter(Task.project_id == project_id)

                if status:
                    query = query.filter(Task.status == status)
                if keyword:
                    query = query.filter(Task.title.ilike(f"%{keyword}%"))

                tasks = query.order_by(Task.due_date.asc()).limit(15).all()
                if not tasks:
                    return "【检索结果】未找到符合条件的任务。"

                scope_desc = "指派给您的待办任务" if (my_tasks_only or not is_admin) else "权限范围内任务"
                res = [f"【{scope_desc}（共 {len(tasks)} 条）】:"]
                for t in tasks:
                    proj_name = t.project.name if t.project else "未知项目"
                    assignee = t.assignee.nickname if t.assignee else "未指派"
                    res.append(
                        f"- [ID:{t.id}] [{proj_name}] {t.title} | 状态: {t.status} | 优先级: {t.priority} | "
                        f"指派人: {assignee} | 工时: {t.actual_hours}/{t.estimated_hours}h | 截止: {t.due_date or '未定'}"
                    )
                return "\n".join(res)
            except Exception as e:
                logger.warning(f"query_tasks tool error: {e}")
                return "【系统提示】任务查询暂时不可用，请稍后重试。"

    @classmethod
    def query_worklogs(
        cls, user: User, db: Session,
        project_id: Optional[int] = None
    ) -> str:
        """Query worklogs. Normal users can strictly only view their own logs."""
        with _timed("query_worklogs"):
            try:
                is_admin = user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in user.roles)
                query = db.query(WorkLog)

                if not is_admin:
                    query = query.filter(WorkLog.user_id == user.id)
                else:
                    accessible_pids = cls.get_user_accessible_project_ids(user, db)
                    query = query.filter(WorkLog.project_id.in_(accessible_pids))

                if project_id:
                    query = query.filter(WorkLog.project_id == project_id)

                logs = query.order_by(WorkLog.log_date.desc()).limit(10).all()
                if not logs:
                    return "【检索结果】未找到相关工时记录。"

                total_hours = sum(l.hours for l in logs)
                res = [f"【工时填报记录（近 {len(logs)} 条，累计 {total_hours} 小时）】:"]
                for l in logs:
                    uname = l.user.nickname if l.user else "用户"
                    pname = l.project.name if l.project else "项目"
                    res.append(
                        f"- [{l.log_date}] {uname} 在【{pname}】投入 {l.hours}h | 状态: {l.status} | 内容: {l.description}"
                    )
                return "\n".join(res)
            except Exception as e:
                logger.warning(f"query_worklogs tool error: {e}")
                return "【系统提示】工时查询暂时不可用，请稍后重试。"

    @classmethod
    def query_issues(
        cls, user: User, db: Session,
        project_id: Optional[int] = None,
        status: Optional[str] = None
    ) -> str:
        """Query issues/defects in accessible projects."""
        with _timed("query_issues"):
            try:
                accessible_pids = cls.get_user_accessible_project_ids(user, db)
                query = db.query(Issue).filter(Issue.project_id.in_(accessible_pids))

                if project_id:
                    if project_id not in accessible_pids:
                        return "【权限拦截】您无权访问该项目的缺陷信息。"
                    query = query.filter(Issue.project_id == project_id)

                if status:
                    query = query.filter(Issue.status == status)

                issues = query.order_by(Issue.created_at.desc()).limit(10).all()
                if not issues:
                    return "【检索结果】未找到相关缺陷记录。"

                res = [f"【缺陷与问题追踪（共 {len(issues)} 项）】:"]
                for i in issues:
                    pname = i.project.name if i.project else "未知项目"
                    assignee = i.assignee.nickname if i.assignee else "未指派"
                    res.append(
                        f"- [ID:{i.id}] [{pname}] {i.title} | 严重度: {i.severity} | 状态: {i.status} | 处理人: {assignee}"
                    )
                return "\n".join(res)
            except Exception as e:
                logger.warning(f"query_issues tool error: {e}")
                return "【系统提示】缺陷查询暂时不可用，请稍后重试。"

    @classmethod
    def query_wiki_docs(
        cls, user: User, db: Session,
        keyword: Optional[str] = None
    ) -> str:
        """Query project wiki documentation and knowledge base."""
        with _timed("query_wiki_docs"):
            try:
                accessible_pids = cls.get_user_accessible_project_ids(user, db)
                query = db.query(Document).filter(
                    (Document.project_id.is_(None)) | (Document.project_id.in_(accessible_pids))
                )

                if keyword:
                    query = query.filter(
                        (Document.title.ilike(f"%{keyword}%")) | (Document.content.ilike(f"%{keyword}%"))
                    )

                docs = query.order_by(Document.updated_at.desc()).limit(8).all()
                if not docs:
                    return "【检索结果】未找到匹配的文档知识库。"

                res = [f"【知识库文档（共 {len(docs)} 篇）】:"]
                for d in docs:
                    pname = d.project.name if d.project else "企业通用知识库"
                    creator = d.creator.nickname if d.creator else "系统"
                    res.append(
                        f"- [{pname}]《{d.title}》| 分类: {d.category} | 作者: {creator} | "
                        f"更新于: {d.updated_at.strftime('%Y-%m-%d')}"
                    )
                return "\n".join(res)
            except Exception as e:
                logger.warning(f"query_wiki_docs tool error: {e}")
                return "【系统提示】文档查询暂时不可用，请稍后重试。"

    @classmethod
    def create_task_by_ai(
        cls, user: User, db: Session,
        title: str,
        project_id: Optional[int] = None,
        priority: str = "MEDIUM",
        description: str = "",
        estimated_hours: float = 4.0
    ) -> str:
        """Create a new task via conversational AI command with permission check."""
        with _timed("create_task_by_ai"):
            try:
                accessible_pids = cls.get_user_accessible_project_ids(user, db)
                if not accessible_pids:
                    return "【权限拦截】您尚未加入任何项目，无法创建任务。"

                target_pid = project_id if (project_id and project_id in accessible_pids) else accessible_pids[0]
                project = db.query(Project).filter(Project.id == target_pid).first()

                new_task = Task(
                    project_id=target_pid,
                    title=title,
                    description=description or f"由 AI 智能小精灵协助创建于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    status="TODO",
                    priority=priority.upper() if priority.upper() in ["LOW", "MEDIUM", "HIGH", "URGENT"] else "MEDIUM",
                    creator_id=user.id,
                    assignee_id=user.id,
                    estimated_hours=estimated_hours,
                    actual_hours=0.0
                )
                db.add(new_task)
                db.commit()
                db.refresh(new_task)

                return (
                    f"✅ **已成功为您创建新任务！**\n"
                    f"- **任务 ID**: #{new_task.id}\n"
                    f"- **所属项目**: {project.name if project else '当前项目'}\n"
                    f"- **任务标题**: {new_task.title}\n"
                    f"- **初始状态**: 待办 (TODO)\n"
                    f"- **优先级**: {new_task.priority}\n"
                    f"- **指派人**: {user.nickname} (当前用户)\n"
                    f"- **预估工时**: {new_task.estimated_hours}h"
                )
            except Exception as e:
                logger.error(f"create_task_by_ai failed: {e}")
                db.rollback()
                return f"【操作失败】任务创建失败，请稍后重试。"

    @classmethod
    def analyze_project_risks(
        cls, user: User, db: Session,
        project_id: Optional[int] = None
    ) -> str:
        """Analyze health, milestone delays, and bottleneck tasks of projects."""
        with _timed("analyze_project_risks"):
            try:
                accessible_pids = cls.get_user_accessible_project_ids(user, db)
                if not accessible_pids:
                    return "【分析结果】您当前未参与任何项目，暂无风险分析数据。"

                target_pid = project_id if (project_id and project_id in accessible_pids) else accessible_pids[0]
                project = db.query(Project).filter(Project.id == target_pid).first()
                if not project:
                    return "【分析结果】未找到指定项目。"

                tasks = db.query(Task).filter(Task.project_id == project.id).all()
                total_tasks = len(tasks)
                done_tasks = len([t for t in tasks if t.status == "DONE"])
                urgent_tasks = [t for t in tasks if t.priority == "URGENT" and t.status != "DONE"]
                issues = db.query(Issue).filter(
                    Issue.project_id == project.id,
                    Issue.status.notin_(["RESOLVED", "CLOSED"])
                ).all()
                milestones = db.query(Milestone).filter(Milestone.project_id == project.id).all()

                analysis = [
                    f"📊 **【{project.name}】AI 智能项目健康度与风险诊断报告**",
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    f"• **项目总体进度**: {project.progress}% | 当前状态: `{project.status}`",
                    f"• **任务完成率**: {done_tasks}/{total_tasks} ({(done_tasks / total_tasks * 100) if total_tasks else 0:.1f}%)",
                    f"• **未解决缺陷数**: {len(issues)} 个待修复 Bug",
                    f"• **紧急阻塞任务**: {len(urgent_tasks)} 项未完成",
                ]

                if urgent_tasks:
                    analysis.append(f"\n⚠️ **高危任务预警**:")
                    for ut in urgent_tasks[:3]:
                        analysis.append(
                            f"  - #{ut.id} {ut.title} (指派人: {ut.assignee.nickname if ut.assignee else '未指派'})"
                        )

                if issues:
                    critical_bugs = [ib for ib in issues if ib.severity in ["CRITICAL", "HIGH"]]
                    if critical_bugs:
                        analysis.append(f"\n🔴 **关键缺陷告警**: 存在 {len(critical_bugs)} 个严重/高危缺陷需优先攻坚！")

                analysis.append(f"\n💡 **AI 优化建议**:")
                if project.progress < 50 and len(urgent_tasks) > 0:
                    analysis.append(f"  1. 建议在敏捷看板中优先将高危任务拖入 IN_PROGRESS 泳道攻坚；")
                    analysis.append(f"  2. 组织每日站会评估工时填报与缺陷修复瓶颈。")
                else:
                    analysis.append(f"  1. 当前项目整体节奏良好，建议按计划推进剩余任务与里程碑验收。")

                return "\n".join(analysis)
            except Exception as e:
                logger.warning(f"analyze_project_risks tool error: {e}")
                return "【系统提示】项目风险分析暂时不可用，请稍后重试。"
