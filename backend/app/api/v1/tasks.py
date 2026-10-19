from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.task import Task, SubTask, TaskComment
from app.models.project import Project, Milestone
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskStatusUpdate, TaskOut, TaskDetailOut,
    SubTaskCreate, SubTaskUpdate, SubTaskOut,
    TaskCommentCreate, TaskCommentOut
)
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user

router = APIRouter()

def build_task_out(t: Task) -> TaskOut:
    creator = t.creator
    assignee = t.assignee
    proj = t.project
    ms = t.milestone

    sub_cnt = len(t.subtasks)
    done_sub_cnt = sum(1 for s in t.subtasks if s.is_completed)
    comment_cnt = len(t.comments)

    return TaskOut(
        id=t.id,
        project_id=t.project_id,
        milestone_id=t.milestone_id,
        title=t.title,
        description=t.description,
        task_type=t.task_type,
        status=t.status,
        priority=t.priority,
        creator_id=t.creator_id,
        assignee_id=t.assignee_id,
        creator_name=creator.nickname if creator else None,
        assignee_name=assignee.nickname if assignee else None,
        assignee_avatar=assignee.avatar if assignee else None,
        project_name=proj.name if proj else None,
        milestone_title=ms.title if ms else None,
        estimated_hours=t.estimated_hours,
        actual_hours=t.actual_hours,
        progress=t.progress,
        start_date=t.start_date,
        due_date=t.due_date,
        order_num=t.order_num,
        tags=t.tags,
        subtask_count=sub_cnt,
        completed_subtask_count=done_sub_cnt,
        comment_count=comment_cnt,
        created_at=t.created_at,
        updated_at=t.updated_at
    )

@router.get("", response_model=ResponseModel[PaginatedData[TaskOut]])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: Optional[int] = None,
    milestone_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if milestone_id:
        query = query.filter(Task.milestone_id == milestone_id)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if task_type:
        query = query.filter(Task.task_type == task_type)
    if keyword:
        query = query.filter(or_(
            Task.title.ilike(f"%{keyword}%"),
            Task.description.ilike(f"%{keyword}%"),
            Task.tags.ilike(f"%{keyword}%")
        ))

    total = query.count()
    tasks = query.order_by(Task.order_num.asc(), Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_task_out(t) for t in tasks]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[TaskOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.get("/kanban", response_model=ResponseModel[dict])
def get_kanban_board(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)

    tasks = query.order_by(Task.order_num.asc(), Task.created_at.desc()).all()
    
    board = {
        "todo": [],
        "in_progress": [],
        "in_review": [],
        "testing": [],
        "done": []
    }

    for t in tasks:
        item = build_task_out(t)
        st = t.status if t.status in board else "todo"
        board[st].append(item)

    return ResponseModel(code=200, message="success", data=board)

@router.get("/{task_id}", response_model=ResponseModel[TaskDetailOut])
def get_task_detail(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    t = db.query(Task).filter(Task.id == task_id).first()
    if not t:
        raise NotFoundException("任务不存在")

    base_out = build_task_out(t)

    subtasks_out = []
    for s in t.subtasks:
        subtasks_out.append(SubTaskOut(
            id=s.id,
            task_id=s.task_id,
            title=s.title,
            is_completed=s.is_completed,
            assignee_id=s.assignee_id,
            assignee_name=s.assignee.nickname if s.assignee else None,
            created_at=s.created_at
        ))

    comments_out = []
    for c in t.comments:
        u = c.user
        comments_out.append(TaskCommentOut(
            id=c.id,
            task_id=c.task_id,
            user_id=c.user_id,
            username=u.username if u else "unknown",
            user_nickname=u.nickname if u else "unknown",
            user_avatar=u.avatar if u else None,
            content=c.content,
            created_at=c.created_at
        ))

    detail = TaskDetailOut(
        **base_out.model_dump(),
        subtasks=subtasks_out,
        comments=comments_out
    )
    return ResponseModel(code=200, message="success", data=detail)

@router.post("", response_model=ResponseModel[TaskOut])
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_task = Task(
        project_id=task_in.project_id,
        milestone_id=task_in.milestone_id,
        title=task_in.title,
        description=task_in.description,
        task_type=task_in.task_type,
        status=task_in.status,
        priority=task_in.priority,
        creator_id=current_user.id,
        assignee_id=task_in.assignee_id,
        estimated_hours=task_in.estimated_hours,
        actual_hours=task_in.actual_hours,
        progress=task_in.progress,
        start_date=task_in.start_date,
        due_date=task_in.due_date,
        order_num=task_in.order_num,
        tags=task_in.tags
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return ResponseModel(code=200, message="任务创建成功", data=build_task_out(new_task))

@router.put("/{task_id}", response_model=ResponseModel[TaskOut])
def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundException("任务不存在")

    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    # Auto calculate progress if status changed to done
    if task.status == "done":
        task.progress = 100

    db.commit()
    db.refresh(task)

    return ResponseModel(code=200, message="任务信息已更新", data=build_task_out(task))

@router.patch("/{task_id}/status", response_model=ResponseModel[TaskOut])
def update_task_status(
    task_id: int,
    status_in: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundException("任务不存在")

    task.status = status_in.status
    if status_in.order_num is not None:
        task.order_num = status_in.order_num
    if task.status == "done":
        task.progress = 100

    db.commit()
    db.refresh(task)
    return ResponseModel(code=200, message="任务状态已更新", data=build_task_out(task))

@router.delete("/{task_id}", response_model=ResponseModel[None])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundException("任务不存在")

    db.delete(task)
    db.commit()
    return ResponseModel(code=200, message="任务已成功删除")

# --- Subtasks and Comments sub-routes ---

@router.post("/{task_id}/subtasks", response_model=ResponseModel[SubTaskOut])
def add_subtask(
    task_id: int,
    sub_in: SubTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sub = SubTask(
        task_id=task_id,
        title=sub_in.title,
        is_completed=sub_in.is_completed,
        assignee_id=sub_in.assignee_id
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return ResponseModel(
        code=200,
        message="子任务添加成功",
        data=SubTaskOut(
            id=sub.id,
            task_id=sub.task_id,
            title=sub.title,
            is_completed=sub.is_completed,
            assignee_id=sub.assignee_id,
            assignee_name=sub.assignee.nickname if sub.assignee else None,
            created_at=sub.created_at
        )
    )

@router.put("/{task_id}/subtasks/{subtask_id}", response_model=ResponseModel[SubTaskOut])
def update_subtask(
    task_id: int,
    subtask_id: int,
    sub_in: SubTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sub = db.query(SubTask).filter(SubTask.id == subtask_id, SubTask.task_id == task_id).first()
    if not sub:
        raise NotFoundException("子任务不存在")

    if sub_in.title is not None:
        sub.title = sub_in.title
    if sub_in.is_completed is not None:
        sub.is_completed = sub_in.is_completed
    if sub_in.assignee_id is not None:
        sub.assignee_id = sub_in.assignee_id

    db.commit()
    db.refresh(sub)
    return ResponseModel(
        code=200,
        message="子任务已更新",
        data=SubTaskOut(
            id=sub.id,
            task_id=sub.task_id,
            title=sub.title,
            is_completed=sub.is_completed,
            assignee_id=sub.assignee_id,
            assignee_name=sub.assignee.nickname if sub.assignee else None,
            created_at=sub.created_at
        )
    )

@router.delete("/{task_id}/subtasks/{subtask_id}", response_model=ResponseModel[None])
def delete_subtask(
    task_id: int,
    subtask_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sub = db.query(SubTask).filter(SubTask.id == subtask_id, SubTask.task_id == task_id).first()
    if not sub:
        raise NotFoundException("子任务不存在")

    db.delete(sub)
    db.commit()
    return ResponseModel(code=200, message="子任务已删除")

@router.post("/{task_id}/comments", response_model=ResponseModel[TaskCommentOut])
def add_task_comment(
    task_id: int,
    comment_in: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comment = TaskComment(
        task_id=task_id,
        user_id=current_user.id,
        content=comment_in.content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return ResponseModel(
        code=200,
        message="评论发表成功",
        data=TaskCommentOut(
            id=comment.id,
            task_id=comment.task_id,
            user_id=comment.user_id,
            username=current_user.username,
            user_nickname=current_user.nickname,
            user_avatar=current_user.avatar,
            content=comment.content,
            created_at=comment.created_at
        )
    )
