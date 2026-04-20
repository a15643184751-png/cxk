from sqlalchemy import Column, Integer, String, Float, Boolean
from ..database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    code = Column(String(32), default="")
    contact = Column(String(64), default="")
    phone = Column(String(32), default="")
    address = Column(String(256), default="")
    license_no = Column(String(64), default="")
    license_url = Column(String(512), default="")
    credit_score = Column(Float, default=0)
    quality_report_url = Column(String(512), default="")
    is_blacklisted = Column(Boolean, default=False)
