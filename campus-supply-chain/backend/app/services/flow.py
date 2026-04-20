from datetime import datetime
from random import randint

from sqlalchemy.orm import Session

from ..models.trace import TraceRecord


PURCHASE_STATUS_LABELS = {
    "pending": "待审批",
    "approved": "待供应商接单",
    "confirmed": "待供应商发货",
    "shipped": "待仓储入库",
    "stocked_in": "待按申请出库",
    "stocked_out": "待创建配送",
    "delivering": "配送中待签收",
    "completed": "已签收完成",
    "rejected": "已驳回",
}

DELIVERY_STATUS_LABELS = {
    "pending": "待发车",
    "loading": "装车中",
    "on_way": "运输中待签收",
    "received": "已签收",
}


def make_flow_code(prefix: str) -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{randint(100, 999)}"


def get_purchase_status_label(status: str) -> str:
    return PURCHASE_STATUS_LABELS.get(status or "", status or "-")


def get_delivery_status_label(status: str) -> str:
    return DELIVERY_STATUS_LABELS.get(status or "", status or "-")


def append_trace(db: Session, trace_key: str, stage: str, content: str):
    db.add(TraceRecord(batch_no=trace_key, stage=stage, content=content[:256]))
