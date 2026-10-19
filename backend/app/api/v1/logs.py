from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.api.deps import get_current_user, PermissionChecker

router = APIRouter()

@router.get("", response_model=ResponseModel[PaginatedData[dict]])
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    module: Optional[str] = None,
    action: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(AuditLog)
    if module:
        query = query.filter(AuditLog.module == module)
    if action:
        query = query.filter(AuditLog.action == action)
    if keyword:
        query = query.filter(or_(
            AuditLog.username.ilike(f"%{keyword}%"),
            AuditLog.details.ilike(f"%{keyword}%"),
            AuditLog.ip.ilike(f"%{keyword}%")
        ))

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "username": l.username,
            "module": l.module,
            "action": l.action,
            "method": l.method,
            "path": l.path,
            "ip": l.ip,
            "status_code": l.status_code,
            "details": l.details,
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for l in logs
    ]

    total_pages = (total + page_size - 1) // page_size
    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[dict](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )
