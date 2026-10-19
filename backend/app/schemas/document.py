from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class DocumentBase(BaseModel):
    project_id: int
    title: str
    category: str = "general"
    content: Optional[str] = None
    version: str = "v1.0"
    file_url: Optional[str] = None

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    file_url: Optional[str] = None

class DocumentOut(DocumentBase):
    id: int
    author_id: int
    author_name: Optional[str] = None
    project_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
