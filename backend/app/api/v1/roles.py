from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import Role, Permission, User
from app.schemas.common import ResponseModel
from app.schemas.user import RoleCreate, RoleUpdate, RoleOut
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user, PermissionChecker

router = APIRouter()

@router.get("", response_model=ResponseModel[List[RoleOut]])
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    roles = db.query(Role).order_by(Role.order_num).all()
    items = []
    for r in roles:
        items.append(RoleOut(
            id=r.id,
            name=r.name,
            code=r.code,
            description=r.description,
            order_num=r.order_num,
            status=r.status,
            created_at=r.created_at,
            permissions=[p.id for p in r.permissions]
        ))
    return ResponseModel(code=200, message="success", data=items)

@router.get("/permissions", response_model=ResponseModel[List[dict]])
def list_all_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    perms = db.query(Permission).order_by(Permission.order_num).all()
    data = [
        {
            "id": p.id,
            "name": p.name,
            "code": p.code,
            "type": p.type,
            "parent_id": p.parent_id,
            "order_num": p.order_num
        }
        for p in perms
    ]
    return ResponseModel(code=200, message="success", data=data)

@router.post("", response_model=ResponseModel[RoleOut])
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:role:add"))
):
    if db.query(Role).filter(Role.code == role_in.code).first():
        raise CustomException(message="角色标识已存在")

    new_role = Role(
        name=role_in.name,
        code=role_in.code,
        description=role_in.description,
        order_num=role_in.order_num,
        status=role_in.status
    )
    if role_in.permission_ids:
        perms = db.query(Permission).filter(Permission.id.in_(role_in.permission_ids)).all()
        new_role.permissions = perms

    db.add(new_role)
    db.commit()
    db.refresh(new_role)

    return ResponseModel(
        code=200,
        message="角色创建成功",
        data=RoleOut(
            id=new_role.id,
            name=new_role.name,
            code=new_role.code,
            description=new_role.description,
            order_num=new_role.order_num,
            status=new_role.status,
            created_at=new_role.created_at,
            permissions=[p.id for p in new_role.permissions]
        )
    )

@router.put("/{role_id}", response_model=ResponseModel[RoleOut])
def update_role(
    role_id: int,
    role_in: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:role:edit"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException("角色不存在")

    if role_in.name is not None:
        role.name = role_in.name
    if role_in.code is not None:
        role.code = role_in.code
    if role_in.description is not None:
        role.description = role_in.description
    if role_in.order_num is not None:
        role.order_num = role_in.order_num
    if role_in.status is not None:
        role.status = role_in.status
    if role_in.permission_ids is not None:
        perms = db.query(Permission).filter(Permission.id.in_(role_in.permission_ids)).all()
        role.permissions = perms

    db.commit()
    db.refresh(role)

    return ResponseModel(
        code=200,
        message="角色更新成功",
        data=RoleOut(
            id=role.id,
            name=role.name,
            code=role.code,
            description=role.description,
            order_num=role.order_num,
            status=role.status,
            created_at=role.created_at,
            permissions=[p.id for p in role.permissions]
        )
    )

@router.delete("/{role_id}", response_model=ResponseModel[None])
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:role:delete"))
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise NotFoundException("角色不存在")
    if role.code == "ADMIN":
        raise CustomException(message="系统内置管理员角色不可删除")

    db.delete(role)
    db.commit()
    return ResponseModel(code=200, message="角色已成功删除")
