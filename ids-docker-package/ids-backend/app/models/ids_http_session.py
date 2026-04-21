from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from ..database import Base


class IDSHTTPSession(Base):
    __tablename__ = "ids_http_sessions"

    id = Column(Integer, primary_key=True, index=True)
    client_ip = Column(String(64), nullable=False, index=True)
    scheme = Column(String(16), default="http")
    host = Column(String(255), default="")
    method = Column(String(16), default="", index=True)
    path = Column(String(1024), default="", index=True)
    query_string = Column(Text, default="")
    route_kind = Column(String(32), default="frontend", index=True)
    upstream_base = Column(String(255), default="")
    upstream_url = Column(String(1024), default="")
    user_agent = Column(String(512), default="")
    request_headers = Column(Text, default="")
    request_body = Column(Text, default="")
    raw_request = Column(Text, default="")
    request_size = Column(Integer, default=0)
    response_status = Column(Integer, default=0, index=True)
    response_headers = Column(Text, default="")
    response_body = Column(Text, default="")
    raw_response = Column(Text, default="")
    response_size = Column(Integer, default=0)
    content_type = Column(String(255), default="")
    duration_ms = Column(Integer, default=0)
    blocked = Column(Integer, default=0, index=True)
    attack_type = Column(String(64), default="", index=True)
    risk_score = Column(Integer, default=0)
    confidence = Column(Integer, default=0)
    incident_id = Column(Integer, nullable=True, index=True)
    response_note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
