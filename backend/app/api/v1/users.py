from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.user import User, Role, Department
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.user import UserCreate, UserUpdate, UserOut, PasswordChangeRequest
from app.core.security import get_password_hash, verify_password
from app.core.exceptions import NotFoundException, CustomException
from app.api.deps import get_current_user, PermissionChecker

router = APIRouter()

@router.get("", response_model=ResponseModel[PaginatedData[UserOut]])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    department_id: Optional[int] = None,
    status: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(User)
    if keyword:
        query = query.filter(or_(
            User.username.ilike(f"%{keyword}%"),
            User.nickname.ilike(f"%{keyword}%"),
            User.email.ilike(f"%{keyword}%")
        ))
    if department_id:
        query = query.filter(User.department_id == department_id)
    if status is not None:
        query = query.filter(User.status == status)

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        items.append(UserOut(
            id=u.id,
            username=u.username,
            nickname=u.nickname,
            email=u.email,
            phone=u.phone,
            avatar=u.avatar,
            position=u.position,
            status=u.status,
            is_superuser=u.is_superuser,
            department_id=u.department_id,
            department_name=u.department.name if u.department else None,
            roles=[r.name for r in u.roles],
            role_ids=[r.id for r in u.roles],
            created_at=u.created_at
        ))

    total_pages = (total + page_size - 1) // page_size
    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[UserOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.get("/all", response_model=ResponseModel[List[UserOut]])
def get_all_active_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    users = db.query(User).filter(User.status == True).all()
    items = []
    for u in users:
        items.append(UserOut(
            id=u.id,
            username=u.username,
            nickname=u.nickname,
            email=u.email,
            phone=u.phone,
            avatar=u.avatar,
            position=u.position,
            status=u.status,
            is_superuser=u.is_superuser,
            department_id=u.department_id,
            department_name=u.department.name if u.department else None,
            roles=[r.name for r in u.roles],
            role_ids=[r.id for r in u.roles],
            created_at=u.created_at
        ))
    return ResponseModel(code=200, message="success", data=items)

@router.post("", response_model=ResponseModel[UserOut])
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:user:add"))
):
    if db.query(User).filter(User.username == user_in.username).first():
        raise CustomException(message="用户名已存在")
    if user_in.email and db.query(User).filter(User.email == user_in.email).first():
        raise CustomException(message="邮箱已被使用")

    new_user = User(
        username=user_in.username,
        nickname=user_in.nickname,
        email=user_in.email,
        phone=user_in.phone,
        avatar=user_in.avatar or f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_in.username}",
        department_id=user_in.department_id,
        position=user_in.position,
        status=user_in.status,
        is_superuser=user_in.is_superuser,
        password_hash=get_password_hash(user_in.password)
    )

    if user_in.role_ids:
        roles = db.query(Role).filter(Role.id.in_(user_in.role_ids)).all()
        new_user.roles = roles

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return ResponseModel(
        code=200,
        message="用户创建成功",
        data=UserOut(
            id=new_user.id,
            username=new_user.username,
            nickname=new_user.nickname,
            email=new_user.email,
            phone=new_user.phone,
            avatar=new_user.avatar,
            position=new_user.position,
            status=new_user.status,
            is_superuser=new_user.is_superuser,
            department_id=new_user.department_id,
            department_name=new_user.department.name if new_user.department else None,
            roles=[r.name for r in new_user.roles],
            role_ids=[r.id for r in new_user.roles],
            created_at=new_user.created_at
        )
    )

@router.put("/{user_id}", response_model=ResponseModel[UserOut])
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:user:edit"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")

    if user_in.nickname is not None:
        user.nickname = user_in.nickname
    if user_in.email is not None:
        user.email = user_in.email
    if user_in.phone is not None:
        user.phone = user_in.phone
    if user_in.avatar is not None:
        user.avatar = user_in.avatar
    if user_in.department_id is not None:
        user.department_id = user_in.department_id
    if user_in.position is not None:
        user.position = user_in.position
    if user_in.status is not None:
        user.status = user_in.status
    if user_in.password:
        user.password_hash = get_password_hash(user_in.password)
    if user_in.role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(user_in.role_ids)).all()
        user.roles = roles

    db.commit()
    db.refresh(user)

    return ResponseModel(
        code=200,
        message="用户更新成功",
        data=UserOut(
            id=user.id,
            username=user.username,
            nickname=user.nickname,
            email=user.email,
            phone=user.phone,
            avatar=user.avatar,
            position=user.position,
            status=user.status,
            is_superuser=user.is_superuser,
            department_id=user.department_id,
            department_name=user.department.name if user.department else None,
            roles=[r.name for r in user.roles],
            role_ids=[r.id for r in user.roles],
            created_at=user.created_at
        )
    )

@router.delete("/{user_id}", response_model=ResponseModel[None])
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(PermissionChecker("system:user:delete"))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("用户不存在")
    if user.is_superuser:
        raise CustomException(message="超级管理员账号不可删除")

    db.delete(user)
    db.commit()
    return ResponseModel(code=200, message="用户已成功删除")

@router.post("/change_password", response_model=ResponseModel[None])
def change_password(
    pwd_in: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(pwd_in.old_password, current_user.password_hash):
        raise CustomException(message="原密码错误")
    
    current_user.password_hash = get_password_hash(pwd_in.new_password)
    db.commit()
    return ResponseModel(code=200, message="密码修改成功，请重新登录")
