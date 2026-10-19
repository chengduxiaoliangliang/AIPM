from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

# Department Schemas
class DepartmentBase(BaseModel):
    name: str
    code: str
    parent_id: Optional[int] = None
    leader: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    order_num: int = 0
    status: bool = True

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    parent_id: Optional[int] = None
    leader: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    order_num: Optional[int] = None
    status: Optional[bool] = None

class DepartmentOut(DepartmentBase):
    id: int
    created_at: datetime
    children: List["DepartmentOut"] = []

    class Config:
        from_attributes = True

# Role Schemas
class RoleBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    order_num: int = 0
    status: bool = True

class RoleCreate(RoleBase):
    permission_ids: List[int] = []

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    order_num: Optional[int] = None
    status: Optional[bool] = None
    permission_ids: Optional[List[int]] = None

class RoleOut(RoleBase):
    id: int
    created_at: datetime
    permissions: List[int] = []

    class Config:
        from_attributes = True

# User Schemas
class UserBase(BaseModel):
    username: str
    nickname: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    department_id: Optional[int] = None
    position: Optional[str] = None
    status: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    password: str
    role_ids: List[int] = []

class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    department_id: Optional[int] = None
    position: Optional[str] = None
    status: Optional[bool] = None
    password: Optional[str] = None
    role_ids: Optional[List[int]] = None

class UserOut(UserBase):
    id: int
    department_name: Optional[str] = None
    roles: List[str] = []
    role_ids: List[int] = []
    created_at: datetime

    class Config:
        from_attributes = True

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
