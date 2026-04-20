from sqlalchemy import Column, Integer, String, ForeignKey
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    real_name = Column(String(64), default="")
    role = Column(String(32), nullable=False)  # system_admin, logistics_admin, warehouse_procurement, campus_supplier, counselor_teacher
    department = Column(String(64), default="")
    phone = Column(String(32), default="")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)  # 供应商角色关联的公司
