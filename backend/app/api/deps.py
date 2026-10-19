from typing import Generator, Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.redis_client import redis_client
from app.core.exceptions import UnauthorizedException, ForbiddenException

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise UnauthorizedException("Invalid token payload")
    except JWTError:
        raise UnauthorizedException("Token invalid or expired")

    # Check if token is blacklisted in Redis
    if redis_client.get(f"blacklist_token:{token}"):
        raise UnauthorizedException("Token has been revoked/logged out")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise UnauthorizedException("User not found")
    if not user.status:
        raise ForbiddenException("User account is disabled")

    return user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise ForbiddenException("Requires superuser privileges")
    return current_user

class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user
        
        user_permissions = set()
        for role in current_user.roles:
            for perm in role.permissions:
                user_permissions.add(perm.code)
        
        if self.required_permission not in user_permissions:
            raise ForbiddenException(f"Permission denied. Required: {self.required_permission}")
        return current_user
