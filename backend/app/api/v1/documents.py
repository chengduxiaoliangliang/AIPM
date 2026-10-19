from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.models.user import User
from app.schemas.common import ResponseModel, PaginatedData
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentOut
from app.core.exceptions import NotFoundException
from app.api.deps import get_current_user

router = APIRouter()

def build_doc_out(d: Document) -> DocumentOut:
    auth = d.author
    proj = d.project
    return DocumentOut(
        id=d.id,
        project_id=d.project_id,
        title=d.title,
        category=d.category,
        content=d.content,
        version=d.version,
        file_url=d.file_url,
        author_id=d.author_id,
        author_name=auth.nickname if auth else None,
        project_name=proj.name if proj else None,
        created_at=d.created_at,
        updated_at=d.updated_at
    )

@router.get("", response_model=ResponseModel[PaginatedData[DocumentOut]])
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    project_id: Optional[int] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Document)
    if project_id:
        query = query.filter(Document.project_id == project_id)
    if category:
        query = query.filter(Document.category == category)
    if keyword:
        query = query.filter(or_(
            Document.title.ilike(f"%{keyword}%"),
            Document.content.ilike(f"%{keyword}%")
        ))

    total = query.count()
    docs = query.order_by(Document.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = [build_doc_out(d) for d in docs]
    total_pages = (total + page_size - 1) // page_size

    return ResponseModel(
        code=200,
        message="success",
        data=PaginatedData[DocumentOut](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    )

@router.get("/{doc_id}", response_model=ResponseModel[DocumentOut])
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise NotFoundException("文档不存在")
    return ResponseModel(code=200, message="success", data=build_doc_out(d))

@router.post("", response_model=ResponseModel[DocumentOut])
def create_document(
    doc_in: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = Document(
        project_id=doc_in.project_id,
        title=doc_in.title,
        category=doc_in.category,
        content=doc_in.content,
        version=doc_in.version,
        file_url=doc_in.file_url,
        author_id=current_user.id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return ResponseModel(code=200, message="文档创建成功", data=build_doc_out(doc))

@router.put("/{doc_id}", response_model=ResponseModel[DocumentOut])
def update_document(
    doc_id: int,
    doc_in: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundException("文档不存在")

    for field, value in doc_in.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)

    return ResponseModel(code=200, message="文档已更新", data=build_doc_out(doc))

@router.delete("/{doc_id}", response_model=ResponseModel[None])
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise NotFoundException("文档不存在")

    db.delete(doc)
    db.commit()
    return ResponseModel(code=200, message="文档已删除")
