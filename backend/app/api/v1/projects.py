import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.project import Project, ProjectMember, Milestone
from app.models.task import Task
from app.models.user import User
from app.models.import_log import ImportLog
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectDetailOut,
    ProjectMemberCreate, ProjectMemberOut,
    MilestoneCreate, MilestoneUpdate, MilestoneOut
)
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user, PermissionChecker
from app.services import project_io

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

# ─── 导入 / 导出 ─────────────────────────────────────────────────────────────
# 注意：这些路由必须定义在 /{project_id} 之前，否则 "import" 会被当成 project_id。

def _xlsx_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.get("/import/template")
def download_import_template(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    current_user: User = Depends(get_current_user),
):
    """下载导入模板。xlsx 为双工作表，csv 为单表（用「类型」列区分项目/任务）。"""
    if format == "csv":
        return StreamingResponse(
            io.BytesIO(project_io.build_csv_template()),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": (
                    "attachment; filename*=UTF-8''"
                    + quote("项目导入模板.csv")
                )
            },
        )
    return _xlsx_response(project_io.build_template(), "项目导入模板.xlsx")


@router.post("/import/preview", response_model=ResponseModel[Dict[str, Any]])
async def preview_import(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解析上传文件：返回识别到的列、自动映射、样例行与校验问题。

    不写库。`mapping` 可选，格式 {"project": {"0": "name"}, "task": {...}}，
    用于覆盖自动映射。
    """
    raw = await file.read()
    overrides = None
    if mapping:
        try:
            overrides = json.loads(mapping)
        except Exception:
            raise CustomException(message="mapping 参数不是合法 JSON")

    try:
        parsed = project_io.parse_import(raw, file.filename or "", overrides)
    except ValueError as exc:
        raise CustomException(message=str(exc))

    rows = parsed.pop("rows")
    issues = project_io.validate_rows(db, rows)
    parsed["issues"] = parsed["issues"] + issues
    parsed["summary"] = {
        "projects": len(rows.get("project", [])),
        "tasks": len(rows.get("task", [])),
        "milestones": len(rows.get("milestone", [])),
        "members": len(rows.get("member", [])),
        "errors": sum(1 for i in parsed["issues"] if i["level"] == "error"),
        "warnings": sum(1 for i in parsed["issues"] if i["level"] == "warning"),
    }
    return ResponseModel(code=200, message="success", data=parsed)


@router.post("/import/execute", response_model=ResponseModel[Dict[str, Any]])
async def execute_import(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行导入。存在 error 级问题时拒绝写入。"""
    raw = await file.read()
    overrides = None
    if mapping:
        try:
            overrides = json.loads(mapping)
        except Exception:
            raise CustomException(message="mapping 参数不是合法 JSON")

    try:
        parsed = project_io.parse_import(raw, file.filename or "", overrides)
    except ValueError as exc:
        raise CustomException(message=str(exc))

    rows = parsed["rows"]
    issues = project_io.validate_rows(db, rows)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warning"]

    def log(status: str, message: str, result: Optional[Dict[str, Any]] = None):
        db.add(ImportLog(
            user_id=current_user.id,
            username=current_user.username,
            filename=(file.filename or "")[:255],
            file_format=parsed.get("format", "xlsx"),
            projects_created=(result or {}).get("projects_created", 0),
            projects_skipped=(result or {}).get("projects_skipped", 0),
            tasks_created=(result or {}).get("tasks_created", 0),
            tasks_skipped=(result or {}).get("tasks_skipped", 0),
            milestones_created=(result or {}).get("milestones_created", 0),
            milestones_skipped=(result or {}).get("milestones_skipped", 0),
            members_created=(result or {}).get("members_created", 0),
            members_skipped=(result or {}).get("members_skipped", 0),
            error_count=len(errors),
            warning_count=len(warnings),
            status=status,
            message=message[:512],
            created_ids=json.dumps(result.get("created_ids") or {}, ensure_ascii=False)
            if result else None,
        ))
        db.commit()

    if errors:
        log("failed", f"存在 {len(errors)} 处错误，未导入")
        return ResponseModel(
            code=400,
            message=f"存在 {len(errors)} 处错误，未导入任何数据",
            data={"issues": errors[:50]},
        )

    try:
        result = project_io.execute_import(db, rows, current_user)
    except Exception as exc:
        db.rollback()
        log("failed", f"导入异常：{exc}")
        raise CustomException(message=f"导入失败：{exc}")

    log("success", "导入成功", result)
    return ResponseModel(
        code=200,
        message=(
            f"导入完成：新增 {result['projects_created']} 个项目、"
            f"{result['tasks_created']} 个任务、"
            f"{result['milestones_created']} 个里程碑、"
            f"{result['members_created']} 个成员"
        ),
        data={**result, "warnings": warnings[:50]},
    )


@router.get("/import/history", response_model=ResponseModel[List[Dict[str, Any]]])
def import_history(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """最近的导入记录（所有人可见，便于团队内追溯）。"""
    rows = (
        db.query(ImportLog)
        .order_by(ImportLog.created_at.desc(), ImportLog.id.desc())
        .limit(limit).all()
    )
    return ResponseModel(code=200, message="success", data=[{
        "id": r.id,
        "username": r.username,
        "filename": r.filename,
        "format": r.file_format,
        "projects_created": r.projects_created,
        "projects_skipped": r.projects_skipped,
        "tasks_created": r.tasks_created,
        "tasks_skipped": r.tasks_skipped,
        "milestones_created": r.milestones_created or 0,
        "milestones_skipped": r.milestones_skipped or 0,
        "members_created": r.members_created or 0,
        "members_skipped": r.members_skipped or 0,
        "error_count": r.error_count,
        "warning_count": r.warning_count,
        "status": r.status,
        "message": r.message,
        "can_rollback": (
            r.status == "success" and bool(r.created_ids) and r.rolled_back_at is None
        ),
        "rolled_back": r.rolled_back_at is not None,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
    } for r in rows])


@router.post("/import/{log_id}/rollback", response_model=ResponseModel[Dict[str, Any]])
def rollback_import_batch(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回滚一次导入：只删除该批次创建的记录。

    如果该批次创建的项目里已经出现了后续新增的内容，会拒绝回滚（避免误删）。
    """
    log = db.query(ImportLog).filter(ImportLog.id == log_id).first()
    if not log:
        raise NotFoundException("导入记录不存在")
    if log.status != "success":
        raise CustomException(message="只有成功的导入才能回滚")
    if log.rolled_back_at:
        raise CustomException(message="该批次已经回滚过了")

    try:
        deleted = project_io.rollback_import(db, log)
    except project_io.RollbackConflict as exc:
        raise CustomException(message=str(exc))
    except ValueError as exc:
        raise CustomException(message=str(exc))

    log.rolled_back_at = datetime.utcnow()
    log.message = (
        f"已回滚：删除 {deleted.get('project', 0)} 个项目、"
        f"{deleted.get('task', 0)} 个任务、"
        f"{deleted.get('milestone', 0)} 个里程碑、"
        f"{deleted.get('member', 0)} 个成员"
    )
    db.commit()

    return ResponseModel(code=200, message=log.message, data={"deleted": deleted})


@router.get("/export")
def export_projects_xlsx(
    ids: str = Query("", description="项目 id，逗号分隔；留空表示导出全部可见项目"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导出项目与任务为一个工作簿（表头与导入模板一致，可再导入）。"""
    query = db.query(Project)
    if ids.strip():
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            raise CustomException(message="ids 参数格式不正确")
        if not id_list:
            raise CustomException(message="未选择项目")
        query = query.filter(Project.id.in_(id_list[:200]))
    projects = query.order_by(Project.id.asc()).limit(200).all()

    if not projects:
        raise NotFoundException("没有可导出的项目")

    data = project_io.export_projects(db, projects)
    name = (
        f"{projects[0].code}-{projects[0].name}.xlsx" if len(projects) == 1
        else f"项目导出-{len(projects)}个.xlsx"
    )
    return _xlsx_response(data, name)


@router.get("/{project_id}/export")
def export_project_xlsx(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出项目及其任务为 xlsx，格式与导入模板一致，可直接再次导入。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise NotFoundException("项目不存在")
    data = project_io.export_project(db, project)
    return _xlsx_response(data, f"{project.code}-{project.name}.xlsx")


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
