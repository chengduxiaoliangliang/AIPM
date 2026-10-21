from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.worklog import WorkLog
from app.models.issue import Issue
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.common import ResponseModel
from app.schemas.stats import (
    DashboardStats, DashboardMetrics, StatusCount, PriorityCount,
    MonthlyTrend, MemberWorkload
)
from app.api.deps import get_current_user

router = APIRouter()


def _recent_months(now: datetime, count: int) -> List[str]:
    """Return the last `count` calendar months as 'YYYY-MM', oldest first.

    Walking the calendar explicitly avoids the drift you get from
    `now - timedelta(days=i * 30)`, which can skip or duplicate a month.
    """
    year, month = now.year, now.month
    keys: List[str] = []
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


@router.get("/dashboard", response_model=ResponseModel[DashboardStats])
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Metrics
    total_projects = db.query(Project).count()
    active_projects = db.query(Project).filter(Project.status.in_(["planning", "in_progress", "testing"])).count()
    
    total_tasks = db.query(Task).count()
    in_progress_tasks = db.query(Task).filter(Task.status == "in_progress").count()
    completed_tasks = db.query(Task).filter(Task.status == "done").count()
    
    pending_approvals = db.query(WorkLog).filter(WorkLog.status == "pending").count()
    total_hours_res = db.query(func.sum(WorkLog.hours)).filter(WorkLog.status == "approved").scalar()
    total_hours = float(total_hours_res or 0.0)
    
    total_issues = db.query(Issue).count()
    open_issues = db.query(Issue).filter(Issue.status.in_(["open", "in_progress"])).count()

    metrics = DashboardMetrics(
        total_projects=total_projects,
        active_projects=active_projects,
        total_tasks=total_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        pending_approvals=pending_approvals,
        total_hours=round(total_hours, 1),
        total_issues=total_issues,
        open_issues=open_issues
    )

    # Project Status Distribution
    status_map = {
        "planning": "规划中",
        "in_progress": "进行中",
        "testing": "测试中",
        "completed": "已交付",
        "suspended": "已挂起"
    }
    proj_status_rows = db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    proj_status_dist = [
        StatusCount(status=st, count=cnt, name=status_map.get(st, st))
        for st, cnt in proj_status_rows
    ]

    # Task Priority Distribution
    priority_map = {
        "urgent": "紧急",
        "high": "高",
        "medium": "中",
        "low": "低"
    }
    task_priority_rows = db.query(Task.priority, func.count(Task.id)).group_by(Task.priority).all()
    task_priority_dist = [
        PriorityCount(priority=pr, count=cnt, name=priority_map.get(pr, pr))
        for pr, cnt in task_priority_rows
    ]

    # ── Monthly trends (last 6 calendar months) ──────────────────────────
    # Aggregated in SQL. The previous version loaded 180 days of rows into
    # Python and strftime'd every row six times, which degrades quickly.
    # NOTE: DATE_FORMAT is MySQL-specific — this project targets MySQL only.
    now = datetime.now()
    month_keys = _recent_months(now, 6)
    since = datetime.strptime(month_keys[0] + "-01", "%Y-%m-%d")

    created_rows = dict(
        db.query(
            func.date_format(Task.created_at, "%Y-%m").label("m"),
            func.count(Task.id),
        ).filter(Task.created_at >= since).group_by("m").all()
    )
    done_rows = dict(
        db.query(
            func.date_format(Task.updated_at, "%Y-%m").label("m"),
            func.count(Task.id),
        ).filter(Task.status == "done", Task.updated_at >= since).group_by("m").all()
    )
    hours_rows = dict(
        db.query(
            func.date_format(WorkLog.log_date, "%Y-%m").label("m"),
            func.sum(WorkLog.hours),
        ).filter(WorkLog.log_date >= since).group_by("m").all()
    )

    # 没有数据的月份就是 0。曾经这里会"兜底"生成随机数字，导致看板展示的是
    # 编造的趋势——管理决策不能建立在假数据上。
    monthly_trends = [
        MonthlyTrend(
            month=key,
            created_tasks=int(created_rows.get(key, 0)),
            completed_tasks=int(done_rows.get(key, 0)),
            logged_hours=round(float(hours_rows.get(key) or 0.0), 1),
        )
        for key in month_keys
    ]

    # ── Member workloads ─────────────────────────────────────────────────
    # Three grouped queries instead of 3 per user (was 18 round-trips for 6).
    users = db.query(User).filter(User.status == True).limit(6).all()
    user_ids = [u.id for u in users]

    task_counts: Dict[int, int] = {}
    done_counts: Dict[int, int] = {}
    hour_sums: Dict[int, float] = {}
    if user_ids:
        task_counts = dict(
            db.query(Task.assignee_id, func.count(Task.id))
            .filter(Task.assignee_id.in_(user_ids))
            .group_by(Task.assignee_id).all()
        )
        done_counts = dict(
            db.query(Task.assignee_id, func.count(Task.id))
            .filter(Task.assignee_id.in_(user_ids), Task.status == "done")
            .group_by(Task.assignee_id).all()
        )
        hour_sums = dict(
            db.query(WorkLog.user_id, func.sum(WorkLog.hours))
            .filter(WorkLog.user_id.in_(user_ids))
            .group_by(WorkLog.user_id).all()
        )

    member_workloads = []
    for u in users:
        u_tasks = int(task_counts.get(u.id, 0))
        u_done = int(done_counts.get(u.id, 0))
        u_hours = float(hour_sums.get(u.id) or 0.0)
        # 无任务时给 0%，而不是 100%——后者会让人误以为"全部完成"
        comp_rate = round(u_done / u_tasks * 100, 1) if u_tasks > 0 else 0.0

        member_workloads.append(MemberWorkload(
            user_id=u.id,
            name=u.nickname,
            avatar=u.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={u.username}",
            task_count=u_tasks,
            logged_hours=round(u_hours, 1),
            completion_rate=comp_rate
        ))

    # Recent activities from AuditLog
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(8).all()
    recent_activities = [
        {
            "id": l.id,
            "username": l.username,
            "module": l.module,
            "action": l.action,
            "details": l.details,
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for l in logs
    ]

    stats = DashboardStats(
        metrics=metrics,
        project_status_dist=proj_status_dist,
        task_priority_dist=task_priority_dist,
        monthly_trends=monthly_trends,
        member_workloads=member_workloads,
        recent_activities=recent_activities
    )

    return ResponseModel(code=200, message="success", data=stats)
