from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worklog import WorkLog
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.worklog import WorkLogCreate, WorkLogApproval, WorkLogOut
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user

router = APIRouter()

def build_worklog_out(w: WorkLog) -> WorkLogOut:
    u = w.user
    p = w.project
    t = w.task
    appr = w.approver
    return WorkLogOut(
        id=w.id,
        project_id=w.project_id,
        task_id=w.task_id,
        user_id=w.user_id,
        log_date=w.log_date,
        hours=w.hours,
        description=w.description,
        status=w.status,
        user_name=u.nickname if u else None,
        user_avatar=u.avatar if u else None,
        project_name=p.name if p else None,
        task_title=t.title if t else None,
        approver_id=w.approver_id,
        approver_name=appr.nickname if appr else None,
        approval_remark=w.approval_remark,
        approved_at=w.approved_at,
        created_at=w.created_at
    )

@router.get("", response_model=ResponseModel[PaginatedData[WorkLogOut]])
def list_worklogs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(WorkLog)
    if project_id:
        query = query.filter(WorkLog.project_id == project_id)
    if user_id:
        query = query.filter(WorkLog.user_id == user_id)
    if status:
        query = query.filter(WorkLog.status == status)

    total = query.count()
    logs = query.order_by(WorkLog.log_date.desc(), WorkLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_worklog_out(w) for w in logs]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[WorkLogOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.post("", response_model=ResponseModel[WorkLogOut])
def create_worklog(
    log_in: WorkLogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    worklog = WorkLog(
        project_id=log_in.project_id,
        task_id=log_in.task_id,
        user_id=current_user.id,
        log_date=log_in.log_date,
        hours=log_in.hours,
        description=log_in.description,
        status="pending"
    )
    db.add(worklog)

    # Accumulate actual hours onto task if attached
    if log_in.task_id:
        task = db.query(Task).filter(Task.id == log_in.task_id).first()
        if task:
            task.actual_hours += log_in.hours

    db.commit()
    db.refresh(worklog)

    return ResponseModel(code=200, message="工时填报成功，等待审批", data=build_worklog_out(worklog))

@router.post("/{worklog_id}/approval", response_model=ResponseModel[WorkLogOut])
def approve_worklog(
    worklog_id: int,
    approval_in: WorkLogApproval,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    worklog = db.query(WorkLog).filter(WorkLog.id == worklog_id).first()
    if not worklog:
        raise NotFoundException("工时记录不存在")

    worklog.status = approval_in.status
    worklog.approver_id = current_user.id
    worklog.approval_remark = approval_in.approval_remark
    worklog.approved_at = datetime.utcnow()

    db.commit()
    db.refresh(worklog)

    return ResponseModel(code=200, message=f"工时已{'通过' if approval_in.status == 'approved' else '驳回'}", data=build_worklog_out(worklog))

@router.delete("/{worklog_id}", response_model=ResponseModel[None])
def delete_worklog(
    worklog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    worklog = db.query(WorkLog).filter(WorkLog.id == worklog_id).first()
    if not worklog:
        raise NotFoundException("工时记录不存在")

    if worklog.user_id != current_user.id and not current_user.is_superuser:
        raise CustomException(message="仅能删除本人填报的工时记录")

    db.delete(worklog)
    db.commit()
    return ResponseModel(code=200, message="工时记录已删除")
