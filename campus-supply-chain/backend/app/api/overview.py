# Supply-chain overview screen API (aggregated read-only data).
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.delivery import Delivery
from ..models.goods import Goods
from ..models.ids_event import IDSEvent
from ..models.purchase import Purchase
from ..models.stock import Inventory
from ..models.supplier import Supplier
from ..models.warning import Warning
from ..services.flow import get_purchase_status_label


router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("/screen")
def get_supply_chain_overview_screen(
    db: Session = Depends(get_db),
):
    goods_total = db.query(Goods).filter(Goods.is_active == True).count()
    supplier_total = db.query(Supplier).count()
    purchase_total = db.query(Purchase).count()
    inventory_qty = int(db.query(func.sum(Inventory.quantity)).scalar() or 0)

    warning_pending = db.query(Warning).filter(Warning.status == "pending").count()
    delivery_on_way = db.query(Delivery).filter(Delivery.status.in_(("pending", "loading", "on_way"))).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ids_today = db.query(IDSEvent).filter(IDSEvent.created_at >= today_start).count()
    ids_blocked = db.query(IDSEvent).filter(IDSEvent.blocked == 1).count()

    purchase_pending = db.query(Purchase).filter(Purchase.status == "pending").count()
    supplier_pending = db.query(Purchase).filter(Purchase.status == "approved").count()
    stock_pending = db.query(Purchase).filter(Purchase.status.in_(("confirmed", "shipped"))).count()
    dispatch_pending = db.query(Purchase).filter(
        Purchase.status.in_(("stocked_in", "stocked_out", "delivering"))
    ).count()
    completed_total = db.query(Purchase).filter(Purchase.status == "completed").count()

    pipeline = [
        {
            "key": "apply",
            "title": "\u91c7\u8d2d\u7533\u8bf7",
            "subtitle": "\u6559\u5e08\u53d1\u8d77 / \u540e\u52e4\u5ba1\u6279",
            "count": purchase_pending,
            "done": purchase_pending == 0,
            "targetPath": "/purchase",
        },
        {
            "key": "supplier",
            "title": "\u4f9b\u5e94\u5546\u63a5\u5355",
            "subtitle": "\u4f9b\u5e94\u5546\u786e\u8ba4 / \u5907\u8d27",
            "count": supplier_pending,
            "done": supplier_pending == 0,
            "targetPath": "/purchase",
        },
        {
            "key": "stock",
            "title": "\u4ed3\u50a8\u6267\u884c",
            "subtitle": "\u5165\u5e93 / \u51fa\u5e93 / \u4ea4\u63a5",
            "count": stock_pending,
            "done": stock_pending == 0,
            "targetPath": "/stock/in",
        },
        {
            "key": "delivery",
            "title": "\u914d\u9001\u7b7e\u6536",
            "subtitle": "\u5728\u9014 / \u7b7e\u6536\u786e\u8ba4",
            "count": dispatch_pending,
            "done": dispatch_pending == 0,
            "targetPath": "/delivery",
        },
        {
            "key": "trace",
            "title": "\u6eaf\u6e90\u95ed\u73af",
            "subtitle": "\u5168\u94fe\u8def\u53ef\u8ffd\u6eaf",
            "count": completed_total,
            "done": completed_total > 0,
            "targetPath": "/trace",
        },
    ]

    warnings = (
        db.query(Warning)
        .order_by(Warning.created_at.desc())
        .limit(5)
        .all()
    )
    warning_list = [
        {
            "id": w.id,
            "material": w.material,
            "level": w.level,
            "status": w.status,
            "desc": w.description or "",
            "created_at": w.created_at.isoformat() if w.created_at else "",
        }
        for w in warnings
    ]

    ids_events = (
        db.query(IDSEvent)
        .order_by(IDSEvent.created_at.desc())
        .limit(6)
        .all()
    )
    ids_recent = [
        {
            "id": e.id,
            "client_ip": e.client_ip,
            "attack_type": e.attack_type,
            "blocked": int(e.blocked or 0),
            "path": e.path or "-",
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in ids_events
    ]

    recent_orders = (
        db.query(Purchase)
        .order_by(Purchase.created_at.desc())
        .limit(8)
        .all()
    )
    order_list = [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "receiver_name": p.receiver_name or "-",
            "destination": p.destination or "-",
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in recent_orders
    ]

    return {
        "stats": [
            {"title": "\u7269\u8d44\u79cd\u7c7b", "value": goods_total, "path": "/goods", "accent": "blue"},
            {"title": "\u4f9b\u5e94\u5546\u6570\u91cf", "value": supplier_total, "path": "/supplier", "accent": "cyan"},
            {"title": "\u91c7\u8d2d\u5355\u603b\u91cf", "value": purchase_total, "path": "/purchase", "accent": "violet"},
            {"title": "\u5e93\u5b58\u603b\u91cf", "value": inventory_qty, "path": "/stock/inventory", "accent": "emerald"},
            {"title": "\u5f85\u5904\u7406\u9884\u8b66", "value": warning_pending, "path": "/warning", "accent": "amber"},
            {"title": "\u5728\u9014\u914d\u9001", "value": delivery_on_way, "path": "/delivery", "accent": "orange"},
        ],
        "pipeline": pipeline,
        "risk": {
            "warningPending": warning_pending,
            "idsToday": ids_today,
            "idsBlocked": ids_blocked,
            "recentWarnings": warning_list,
            "recentEvents": ids_recent,
        },
        "recentOrders": order_list,
        "updatedAt": datetime.utcnow().isoformat(),
    }

