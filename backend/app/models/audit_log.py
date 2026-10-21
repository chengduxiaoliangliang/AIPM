from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from app.database import Base

class AuditLog(Base):
    __tablename__ = "sys_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(64), nullable=True)
    module = Column(String(64), nullable=False)      # e.g., 'Project', 'Task', 'Auth'
    action = Column(String(64), nullable=False)      # e.g., 'Create', 'Update', 'Delete', 'Login'
    method = Column(String(16), nullable=True)       # 'GET', 'POST', 'PUT', 'DELETE'
    path = Column(String(255), nullable=True)
    ip = Column(String(64), nullable=True)
    status_code = Column(Integer, default=200)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
