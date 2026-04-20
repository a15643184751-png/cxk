from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from ..database import Base


class TraceRecord(Base):
    __tablename__ = "trace_records"

    id = Column(Integer, primary_key=True, index=True)
    batch_no = Column(String(64), nullable=False, index=True)
    stage = Column(String(64), nullable=False)  # 供应商, 采购, 入库, 仓储, 配送
    content = Column(String(256), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
