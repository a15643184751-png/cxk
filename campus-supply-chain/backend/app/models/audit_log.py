from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    user_name = Column(String(64), default="")
    user_role = Column(String(64), default="")
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), default="", index=True)
    target_id = Column(String(64), default="", index=True)
    detail = Column(String(512), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
