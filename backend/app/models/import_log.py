from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class ImportLog(Base):
    """一次项目导入的结果记录。

    导入是批量写操作，出问题需要能追溯"谁、什么时候、导了什么、结果如何"。
    """
    __tablename__ = "pm_import_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    username = Column(String(64), nullable=True)
    filename = Column(String(255), nullable=True)
    file_format = Column(String(16), default="xlsx")

    projects_created = Column(Integer, default=0)
    projects_skipped = Column(Integer, default=0)
    tasks_created = Column(Integer, default=0)
    tasks_skipped = Column(Integer, default=0)
    milestones_created = Column(Integer, default=0)
    milestones_skipped = Column(Integer, default=0)
    members_created = Column(Integer, default=0)
    members_skipped = Column(Integer, default=0)

    error_count = Column(Integer, default=0)
    warning_count = Column(Integer, default=0)
    status = Column(String(16), default="success")  # success / failed
    message = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
