from sqlalchemy import Column, Integer, String

from ..database import Base


class User(Base):
    __tablename__ = "ids_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    real_name = Column(String(64), default="")
    role = Column(String(32), nullable=False)  # ids_admin / ids_operator / ids_auditor / ids_viewer
    department = Column(String(64), default="")
    phone = Column(String(32), default="")
