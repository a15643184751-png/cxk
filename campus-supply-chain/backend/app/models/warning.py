from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from ..database import Base


class Warning(Base):
    __tablename__ = "warnings"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(32), default="medium")  # high, medium, low
    material = Column(String(128), nullable=False)
    description = Column(String(256), default="")
    status = Column(String(32), default="pending")  # pending, handled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
