from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.issue import Issue
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.issue import IssueCreate, IssueUpdate, IssueOut
from app.core.exceptions import NotFoundException
from app.api.deps import get_current_user

router = APIRouter()

def build_issue_out(i: Issue) -> IssueOut:
    rep = i.reporter
    ass = i.assignee
    proj = i.project
    t = i.task
    return IssueOut(
        id=i.id,
        project_id=i.project_id,
        task_id=i.task_id,
        title=i.title,
        description=i.description,
        severity=i.severity,
        priority=i.priority,
        status=i.status,
        assignee_id=i.assignee_id,
        reporter_id=i.reporter_id,
        reporter_name=rep.nickname if rep else None,
        assignee_name=ass.nickname if ass else None,
        project_name=proj.name if proj else None,
        task_title=t.title if t else None,
        resolution=i.resolution,
        created_at=i.created_at,
        updated_at=i.updated_at
    )

@router.get("", response_model=ResponseModel[PaginatedData[IssueOut]])
def list_issues(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Issue)
    if project_id:
        query = query.filter(Issue.project_id == project_id)
    if status:
        query = query.filter(Issue.status == status)
    if severity:
        query = query.filter(Issue.severity == severity)
    if priority:
        query = query.filter(Issue.priority == priority)
    if assignee_id:
        query = query.filter(Issue.assignee_id == assignee_id)
    if keyword:
        query = query.filter(or_(
            Issue.title.ilike(f"%{keyword}%"),
            Issue.description.ilike(f"%{keyword}%")
        ))

    total = query.count()
    issues = query.order_by(Issue.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_issue_out(i) for i in issues]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[IssueOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.post("", response_model=ResponseModel[IssueOut])
def create_issue(
    issue_in: IssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue = Issue(
        project_id=issue_in.project_id,
        task_id=issue_in.task_id,
        title=issue_in.title,
        description=issue_in.description,
        severity=issue_in.severity,
        priority=issue_in.priority,
        status=issue_in.status,
        assignee_id=issue_in.assignee_id,
        reporter_id=current_user.id
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    return ResponseModel(code=200, message="缺陷工单创建成功", data=build_issue_out(issue))

@router.put("/{issue_id}", response_model=ResponseModel[IssueOut])
def update_issue(
    issue_id: int,
    issue_in: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise NotFoundException("缺陷工单不存在")

    for field, value in issue_in.model_dump(exclude_unset=True).items():
        setattr(issue, field, value)

    db.commit()
    db.refresh(issue)

    return ResponseModel(code=200, message="缺陷工单已更新", data=build_issue_out(issue))

@router.delete("/{issue_id}", response_model=ResponseModel[None])
def delete_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise NotFoundException("缺陷工单不存在")

    db.delete(issue)
    db.commit()
    return ResponseModel(code=200, message="缺陷工单已删除")
