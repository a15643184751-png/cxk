from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from ..database import Base


class StockIn(Base):
    __tablename__ = "stock_ins"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False)
    goods_name = Column(String(128), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(32), default="")
    batch_no = Column(String(64), default="")
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StockOut(Base):
    __tablename__ = "stock_outs"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), nullable=False)
    goods_name = Column(String(128), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(32), default="")
    batch_no = Column(String(64), default="")
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    destination = Column(String(200), default="")
    receiver_name = Column(String(50), default="")
    handoff_code = Column(String(64), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, index=True)
    goods_name = Column(String(128), nullable=False)
    category = Column(String(64), default="")
    quantity = Column(Float, default=0)
    unit = Column(String(32), default="")
    batch_no = Column(String(64), default="")
    shelf_life_days = Column(Integer, default=365)
    produced_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
