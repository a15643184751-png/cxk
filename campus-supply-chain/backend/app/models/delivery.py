from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    delivery_no = Column(String(50), unique=True, nullable=False, index=True)
    stock_out_id = Column(Integer, ForeignKey("stock_outs.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    deliverer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    receiver_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    destination = Column(String(200), nullable=False)
    status = Column(String(20), default="pending")  # pending, loading, on_way, received
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    actual_at = Column(DateTime(timezone=True), nullable=True)
    receiver_name = Column(String(50), default="")
    handoff_code = Column(String(64), default="")
    confirmed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    remark = Column(Text, default="")
    sign_remark = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
