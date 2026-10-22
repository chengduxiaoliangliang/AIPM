from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


class ImportPreset(Base):
    """保存下来的列映射，用于重复导入同一来源的文件。

    场景：用户从某个外部系统定期导出表格，列名固定但和我们的别名对不上，
    每次都要手动映射一遍。存成预设后一键套用。

    `signature` 是文件表头的指纹，用来判断某个预设是否适用于当前文件。
    """
    __tablename__ = "pm_import_presets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("sys_users.id"), nullable=True)
    username = Column(String(64), nullable=True)
    name = Column(String(64), nullable=False)
    signature = Column(String(64), nullable=True, index=True)
    mapping = Column(Text, nullable=False)  # JSON: {sheet: {列下标: 字段key}}
    created_at = Column(DateTime, default=datetime.utcnow)
