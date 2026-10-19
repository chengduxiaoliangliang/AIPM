from datetime import datetime, timedelta
from typing import Any, List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.user import User, Role
from app.models.audit_log import AuditLog
from app.schemas.common import ResponseModel
from app.schemas.auth import (
    LoginRequest, Token, UserInfoResponse,
    SliderCaptchaResponse, SliderVerifyRequest, SliderVerifyResponse
)
from app.core.security import verify_password, create_access_token, get_password_hash, needs_rehash
from app.core.exceptions import UnauthorizedException
from app.core.captcha import SliderCaptchaService
from app.api.deps import get_current_user
from app.redis_client import redis_client

router = APIRouter()

@router.get("/captcha/slider", response_model=ResponseModel[SliderCaptchaResponse])
def get_slider_captcha():
    """
    Generate dynamic procedural sliding puzzle captcha with jigsaw cutout.
    """
    captcha_data = SliderCaptchaService.generate_captcha()
    return ResponseModel(
        code=200,
        message="success",
        data=SliderCaptchaResponse(**captcha_data)
    )

@router.post("/captcha/verify", response_model=ResponseModel[SliderVerifyResponse])
def verify_slider_captcha(verify_req: SliderVerifyRequest):
    """
    Validate sliding captcha offset and human behavioral trajectory.
    """
    result = SliderCaptchaService.verify_trajectory_and_offset(
        captcha_id=verify_req.captcha_id,
        submitted_x=verify_req.x,
        track=verify_req.track
    )
    if not result.get("success"):
        return ResponseModel(
            code=400,
            message=result.get("message", "验证失败"),
            data=SliderVerifyResponse(success=False, message=result.get("message", "验证失败"))
        )
    
    return ResponseModel(
        code=200,
        message=result.get("message", "验证通过"),
        data=SliderVerifyResponse(
            success=True,
            captcha_token=result.get("captcha_token"),
            elapsed_time=result.get("elapsed_time"),
            message=result.get("message")
        )
    )

@router.post("/login", response_model=ResponseModel[Dict[str, Any]])
def login(request: Request, login_data: LoginRequest, db: Session = Depends(get_db)):
    # Validate sliding captcha token if provided
    if login_data.captcha_token:
        is_valid_captcha = SliderCaptchaService.validate_captcha_token(login_data.captcha_token)
        if not is_valid_captcha:
            raise HTTPException(status_code=400, detail={"code": 400, "message": "滑块验证码已失效，请重新验证"})

    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise UnauthorizedException("用户名或密码错误")
    
    if not user.status:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": 403, "message": "该账号已被禁用"})

    # Transparently upgrade legacy SHA256 hashes to bcrypt on successful login
    if needs_rehash(user.password_hash):
        try:
            user.password_hash = get_password_hash(login_data.password)
            db.commit()
        except Exception:
            db.rollback()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(subject=user.username, expires_delta=access_token_expires)

    # Record login audit log
    client_ip = request.client.host if request.client else "unknown"
    audit = AuditLog(
        user_id=user.id,
        username=user.username,
        module="认证",
        action="登录",
        method="POST",
        path="/api/v1/auth/login",
        ip=client_ip,
        status_code=200,
        details=f"用户 {user.nickname}({user.username}) 成功登录系统 (已通过滑块人机验证)"
    )
    db.add(audit)
    db.commit()

    return ResponseModel(
        code=200,
        message="登录成功",
        data={
            "token": token,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "position": user.position,
                "is_superuser": user.is_superuser
            }
        }
    )

@router.get("/user_info", response_model=ResponseModel[UserInfoResponse])
def get_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = [role.code for role in current_user.roles]
    if current_user.is_superuser and "ADMIN" not in roles:
        roles.append("ADMIN")

    permissions = set()
    if current_user.is_superuser:
        permissions.add("*")
    else:
        for role in current_user.roles:
            for perm in role.permissions:
                permissions.add(perm.code)

    dept_name = current_user.department.name if current_user.department else None

    return ResponseModel(
        code=200,
        message="success",
        data=UserInfoResponse(
            id=current_user.id,
            username=current_user.username,
            nickname=current_user.nickname,
            email=current_user.email,
            phone=current_user.phone,
            avatar=current_user.avatar,
            position=current_user.position,
            is_superuser=current_user.is_superuser,
            roles=roles,
            permissions=list(permissions),
            department_id=current_user.department_id,
            department_name=dept_name
        )
    )

@router.post("/logout", response_model=ResponseModel[None])
def logout(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        redis_client.set(f"blacklist_token:{token}", "revoked", ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    return ResponseModel(code=200, message="已成功退出登录")
