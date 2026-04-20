from sqlalchemy import Column, Integer, String, Boolean, Text
from ..database import Base


class Goods(Base):
    __tablename__ = "goods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    category = Column(String(64), default="")  # 食材, 防疫, 办公, 实验
    spec = Column(String(64), default="")
    unit = Column(String(32), default="")
    safety_level = Column(String(32), default="medium")  # critical, high, medium, low
    shelf_life_days = Column(Integer, default=365)
    health_standard = Column(Text, default="")
    description = Column(String(512), default="")
    is_active = Column(Boolean, default=True)
