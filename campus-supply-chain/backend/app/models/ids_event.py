"""IDS 入侵检测事件表：抓包解析、特征匹配、攻击识别、留痕归档"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base


class IDSEvent(Base):
    __tablename__ = "ids_events"

    id = Column(Integer, primary_key=True, index=True)
    client_ip = Column(String(64), nullable=False, index=True)
    attack_type = Column(String(64), nullable=False, index=True)  # sql_injection, xss, path_traversal, cmd_injection, scanner, etc.
    signature_matched = Column(String(128), default="")
    method = Column(String(16), default="")
    path = Column(String(512), default="")
    query_snippet = Column(Text, default="")
    body_snippet = Column(Text, default="")
    user_agent = Column(String(512), default="")
    headers_snippet = Column(Text, default="")
    blocked = Column(Integer, default=1)  # 1=已封禁 0=仅记录
    firewall_rule = Column(String(256), default="")  # 防火墙规则名
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    archived = Column(Integer, default=0)  # 0=未归档 1=已归档
    status = Column(String(32), default="new", index=True)  # new / investigating / mitigated / false_positive / closed
    review_note = Column(Text, default="")
    action_taken = Column(String(128), default="")
    risk_score = Column(Integer, default=0)  # 0-100
    confidence = Column(Integer, default=0)  # 0-100
    hit_count = Column(Integer, default=0)
    detect_detail = Column(Text, default="")  # json string of matched signatures
    ai_analysis = Column(Text, default="")  # LLM 研判全文
    ai_risk_level = Column(String(32), default="")  # high / medium / low / unknown
    ai_confidence = Column(Integer, default=0)  # 0-100
    ai_analyzed_at = Column(DateTime(timezone=True), nullable=True)
