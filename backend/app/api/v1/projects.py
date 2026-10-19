from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.project import Project, ProjectMember, Milestone
from app.models.task import Task
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectDetailOut,
    ProjectMemberCreate, ProjectMemberOut,
    MilestoneCreate, MilestoneUpdate, MilestoneOut
)
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user, PermissionChecker

router = APIRouter()

@router.get("", response_model=ResponseModel[PaginatedData[ProjectOut]])
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Project)
    if keyword:
        query = query.filter(or_(
            Project.name.ilike(f"%{keyword}%"),
            Project.code.ilike(f"%{keyword}%"),
            Project.description.ilike(f"%{keyword}%")
        ))
    if status:
        query = query.filter(Project.status == status)
    if priority:
        query = query.filter(Project.priority == priority)

    total = query.count()
    projects = query.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for p in projects:
        owner = p.owner
        member_cnt = len(p.members)
        task_cnt = db.query(Task).filter(Task.project_id == p.id).count()
        completed_task_cnt = db.query(Task).filter(Task.project_id == p.id, Task.status == "done").count()
        
        items.append(ProjectOut(
            id=p.id,
            name=p.name,
            code=p.code,
            description=p.description,
            owner_id=p.owner_id,
            owner_name=owner.nickname if owner else None,
            owner_avatar=owner.avatar if owner else None,
            status=p.status,
            priority=p.priority,
            budget=p.budget,
            consumed_budget=p.consumed_budget,
            progress=p.progress,
            health=p.health,
            start_date=p.start_date,
            end_date=p.end_date,
            cover_image=p.cover_image,
            member_count=member_cnt,
            task_count=task_cnt,
            completed_task_count=completed_task_cnt,
            created_at=p.created_at,
            updated_at=p.updated_at
        ))

    total_pages = (total + page_size - 1) // page_size
    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[ProjectOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.get("/all", response_model=ResponseModel[List[ProjectOut]])
def get_all_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects = db.query(Project).all()
    items = []
    for p in projects:
        owner = p.owner
        items.append(ProjectOut(
            id=p.id,
            name=p.name,
            code=p.code,
            description=p.description,
            owner_id=p.owner_id,
            owner_name=owner.nickname if owner else None,
            owner_avatar=owner.avatar if owner else None,
            status=p.status,
            priority=p.priority,
            budget=p.budget,
            consumed_budget=p.consumed_budget,
            progress=p.progress,
            health=p.health,
            start_date=p.start_date,
            end_date=p.end_date,
            cover_image=p.cover_image,
            member_count=len(p.members),
            task_count=0,
            completed_task_count=0,
            created_at=p.created_at,
            updated_at=p.updated_at
        ))
    return ResponseModel(code=200, message="success", data=items)

@router.get("/{project_id}", response_model=ResponseModel[ProjectDetailOut])
def get_project_detail(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise NotFoundException("项目不存在")

    owner = p.owner
    task_cnt = db.query(Task).filter(Task.project_id == p.id).count()
    completed_task_cnt = db.query(Task).filter(Task.project_id == p.id, Task.status == "done").count()

    members_out = []
    for m in p.members:
        u = m.user
        if u:
            members_out.append(ProjectMemberOut(
                id=m.id,
                project_id=m.project_id,
                user_id=m.user_id,
                project_role=m.project_role,
                username=u.username,
                nickname=u.nickname,
                avatar=u.avatar,
                position=u.position,
                joined_at=m.joined_at
            ))

    milestones_out = []
    for ms in p.milestones:
        milestones_out.append(MilestoneOut(
            id=ms.id,
            project_id=ms.project_id,
            title=ms.title,
            description=ms.description,
            due_date=ms.due_date,
            status=ms.status,
            order_num=ms.order_num,
            reached_at=ms.reached_at,
            created_at=ms.created_at
        ))

    detail = ProjectDetailOut(
        id=p.id,
        name=p.name,
        code=p.code,
        description=p.description,
        owner_id=p.owner_id,
        owner_name=owner.nickname if owner else None,
        owner_avatar=owner.avatar if owner else None,
        status=p.status,
        priority=p.priority,
        budget=p.budget,
        consumed_budget=p.consumed_budget,
        progress=p.progress,
        health=p.health,
        start_date=p.start_date,
        end_date=p.end_date,
        cover_image=p.cover_image,
        member_count=len(p.members),
        task_count=task_cnt,
        completed_task_count=completed_task_cnt,
        created_at=p.created_at,
        updated_at=p.updated_at,
        members=members_out,
        milestones=milestones_out
    )
    return ResponseModel(code=200, message="success", data=detail)

@router.post("", response_model=ResponseModel[ProjectOut])
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if db.query(Project).filter(Project.code == project_in.code).first():
        raise CustomException(message="项目代号已存在")

    new_project = Project(
        name=project_in.name,
        code=project_in.code,
        description=project_in.description,
        owner_id=project_in.owner_id or current_user.id,
        status=project_in.status,
        priority=project_in.priority,
        budget=project_in.budget,
        progress=project_in.progress,
        health=project_in.health,
        start_date=project_in.start_date,
        end_date=project_in.end_date,
        cover_image=project_in.cover_image
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    # Add owner as project manager member
    db.add(ProjectMember(
        project_id=new_project.id,
        user_id=new_project.owner_id,
        project_role="pm"
    ))

    # Add extra members if provided
    for uid in project_in.member_user_ids:
        if uid != new_project.owner_id:
            db.add(ProjectMember(
                project_id=new_project.id,
                user_id=uid,
                project_role="developer"
            ))

    db.commit()
    db.refresh(new_project)

    owner = new_project.owner
    return ResponseModel(
        code=200,
        message="项目创建成功",
        data=ProjectOut(
            id=new_project.id,
            name=new_project.name,
            code=new_project.code,
            description=new_project.description,
            owner_id=new_project.owner_id,
            owner_name=owner.nickname if owner else None,
            owner_avatar=owner.avatar if owner else None,
            status=new_project.status,
            priority=new_project.priority,
            budget=new_project.budget,
            consumed_budget=new_project.consumed_budget,
            progress=new_project.progress,
            health=new_project.health,
            start_date=new_project.start_date,
            end_date=new_project.end_date,
            cover_image=new_project.cover_image,
            member_count=len(new_project.members),
            task_count=0,
            completed_task_count=0,
            created_at=new_project.created_at,
            updated_at=new_project.updated_at
        )
    )

@router.put("/{project_id}", response_model=ResponseModel[ProjectOut])
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundException("项目不存在")

    for field, value in project_in.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    owner = project.owner
    task_cnt = db.query(Task).filter(Task.project_id == project.id).count()
    completed_task_cnt = db.query(Task).filter(Task.project_id == project.id, Task.status == "done").count()

    return ResponseModel(
        code=200,
        message="项目信息已更新",
        data=ProjectOut(
            id=project.id,
            name=project.name,
            code=project.code,
            description=project.description,
            owner_id=project.owner_id,
            owner_name=owner.nickname if owner else None,
            owner_avatar=owner.avatar if owner else None,
            status=project.status,
            priority=project.priority,
            budget=project.budget,
            consumed_budget=project.consumed_budget,
            progress=project.progress,
            health=project.health,
            start_date=project.start_date,
            end_date=project.end_date,
            cover_image=project.cover_image,
            member_count=len(project.members),
            task_count=task_cnt,
            completed_task_count=completed_task_cnt,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
    )

@router.delete("/{project_id}", response_model=ResponseModel[None])
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundException("项目不存在")

    db.delete(project)
    db.commit()
    return ResponseModel(code=200, message="项目已成功删除")

# --- Members and Milestones sub-routes ---

@router.post("/{project_id}/members", response_model=ResponseModel[None])
def add_project_member(
    project_id: int,
    member_in: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    exists = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_in.user_id
    ).first()
    if exists:
        raise CustomException(message="该用户已是项目成员")

    member = ProjectMember(
        project_id=project_id,
        user_id=member_in.user_id,
        project_role=member_in.project_role
    )
    db.add(member)
    db.commit()
    return ResponseModel(code=200, message="成员添加成功")

@router.delete("/{project_id}/members/{member_id}", response_model=ResponseModel[None])
def remove_project_member(
    project_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    member = db.query(ProjectMember).filter(
        ProjectMember.id == member_id,
        ProjectMember.project_id == project_id
    ).first()
    if not member:
        raise NotFoundException("成员不存在")

    db.delete(member)
    db.commit()
    return ResponseModel(code=200, message="成员已移出项目")

@router.post("/{project_id}/milestones", response_model=ResponseModel[MilestoneOut])
def add_milestone(
    project_id: int,
    ms_in: MilestoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ms = Milestone(
        project_id=project_id,
        title=ms_in.title,
        description=ms_in.description,
        due_date=ms_in.due_date,
        status=ms_in.status,
        order_num=ms_in.order_num
    )
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return ResponseModel(
        code=200,
        message="里程碑创建成功",
        data=MilestoneOut(
            id=ms.id,
            project_id=ms.project_id,
            title=ms.title,
            description=ms.description,
            due_date=ms.due_date,
            status=ms.status,
            order_num=ms.order_num,
            reached_at=ms.reached_at,
            created_at=ms.created_at
        )
    )

@router.put("/{project_id}/milestones/{milestone_id}", response_model=ResponseModel[MilestoneOut])
def update_milestone(
    project_id: int,
    milestone_id: int,
    ms_in: MilestoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ms = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.project_id == project_id
    ).first()
    if not ms:
        raise NotFoundException("里程碑不存在")

    for field, value in ms_in.model_dump(exclude_unset=True).items():
        setattr(ms, field, value)

    db.commit()
    db.refresh(ms)
    return ResponseModel(
        code=200,
        message="里程碑已更新",
        data=MilestoneOut(
            id=ms.id,
            project_id=ms.project_id,
            title=ms.title,
            description=ms.description,
            due_date=ms.due_date,
            status=ms.status,
            order_num=ms.order_num,
            reached_at=ms.reached_at,
            created_at=ms.created_at
        )
    )

@router.delete("/{project_id}/milestones/{milestone_id}", response_model=ResponseModel[None])
def delete_milestone(
    project_id: int,
    milestone_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ms = db.query(Milestone).filter(
        Milestone.id == milestone_id,
        Milestone.project_id == project_id
    ).first()
    if not ms:
        raise NotFoundException("里程碑不存在")

    db.delete(ms)
    db.commit()
    return ResponseModel(code=200, message="里程碑已删除")
