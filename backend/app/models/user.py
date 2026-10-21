from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Text
from sqlalchemy.orm import relationship
from app.database import Base

# Association table for User <-> Role (Many-to-Many)
user_role_table = Table(
    "sys_user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("sys_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("sys_roles.id", ondelete="CASCADE"), primary_key=True)
)

# Association table for Role <-> Permission (Many-to-Many)
role_permission_table = Table(
    "sys_role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("sys_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("sys_permissions.id", ondelete="CASCADE"), primary_key=True)
)

class Department(Base):
    __tablename__ = "sys_departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(64), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("sys_departments.id"), nullable=True)
    leader = Column(String(64), nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(128), nullable=True)
    order_num = Column(Integer, default=0)
    status = Column(Boolean, default=True)  # True = Active, False = Disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    parent = relationship("Department", remote_side=[id], backref="children")
    users = relationship("User", back_populates="department")

class Role(Base):
    __tablename__ = "sys_roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(64), unique=True, nullable=False)  # e.g., 'ADMIN', 'PM', 'DEV', 'QA'
    description = Column(String(255), nullable=True)
    order_num = Column(Integer, default=0)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users = relationship("User", secondary=user_role_table, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permission_table, back_populates="roles")

class Permission(Base):
    __tablename__ = "sys_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), nullable=False)
    code = Column(String(128), unique=True, nullable=False)  # e.g., 'project:create', 'task:update'
    type = Column(String(32), default="menu")  # 'menu', 'button', 'api'
    parent_id = Column(Integer, ForeignKey("sys_permissions.id"), nullable=True)
    path = Column(String(255), nullable=True)
    component = Column(String(255), nullable=True)
    icon = Column(String(64), nullable=True)
    order_num = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    roles = relationship("Role", secondary=role_permission_table, back_populates="permissions")

class User(Base):
    __tablename__ = "sys_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    nickname = Column(String(64), nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=True)
    phone = Column(String(32), nullable=True)
    password_hash = Column(String(255), nullable=False)
    avatar = Column(String(255), nullable=True)
    department_id = Column(Integer, ForeignKey("sys_departments.id"), nullable=True)
    position = Column(String(64), nullable=True)  # e.g., 'Senior Frontend Engineer'
    status = Column(Boolean, default=True)  # True = Active, False = Banned
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    department = relationship("Department", back_populates="users")
    roles = relationship("Role", secondary=user_role_table, back_populates="users")
