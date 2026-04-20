"""工作台真实数据 API：统计、预警、待办、图表"""
from collections import OrderedDict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_

from ..database import get_db
from ..models.user import User
from ..models.goods import Goods
from ..models.supplier import Supplier
from ..models.purchase import Purchase
from ..models.stock import StockIn, StockOut, Inventory
from ..models.warning import Warning
from ..models.audit_log import AuditLog
from ..models.delivery import Delivery
from ..models.ids_event import IDSEvent
from ..api.deps import get_current_user, require_roles, normalize_role
from ..api.supplier import _resolve_supplier_id
from ..services.flow import get_delivery_status_label, get_purchase_status_label


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _pending_outbound_documents(db: Session, limit: int = 8) -> list[dict]:
    """已入库待出库的申领单，供仓储工作台/大屏展示「出库备货单」明细。"""
    rows = (
        db.query(Purchase)
        .filter(Purchase.status == "stocked_in")
        .order_by(Purchase.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for p in rows:
        applicant = db.query(User).filter(User.id == p.applicant_id).first() if p.applicant_id else None
        role = normalize_role(applicant.role) if applicant else ""
        out.append(
            {
                "purchase_id": p.id,
                "order_no": p.order_no,
                "destination": p.destination or "",
                "receiver_name": p.receiver_name or "",
                "applicant_name": (applicant.real_name or applicant.username) if applicant else "-",
                "applicant_role": role,
                "material_type": p.material_type or "",
                "created_at": p.created_at.isoformat() if p.created_at else "",
                "lines": [
                    {"goods_name": i.goods_name, "quantity": float(i.quantity), "unit": i.unit or "件"}
                    for i in (p.items or [])
                ],
            }
        )
    return out


def _recent_outbound_slips(db: Session, limit: int = 8) -> list[dict]:
    """按出库单号聚合的已出库记录（教师申领经仓储确认出库后生成）。"""
    items = db.query(StockOut).order_by(StockOut.created_at.desc()).limit(240).all()
    by_order: OrderedDict[str, dict] = OrderedDict()
    for x in items:
        if x.order_no in by_order:
            by_order[x.order_no]["lines"].append(
                {
                    "goods_name": x.goods_name,
                    "quantity": float(x.quantity),
                    "unit": x.unit or "件",
                    "batch_no": x.batch_no or "",
                }
            )
            continue
        by_order[x.order_no] = {
            "stock_out_order_no": x.order_no,
            "purchase_id": x.purchase_id,
            "purchase_order_no": "",
            "destination": x.destination or "",
            "receiver_name": x.receiver_name or "",
            "handoff_code": x.handoff_code or "",
            "created_at": x.created_at.isoformat() if x.created_at else "",
            "lines": [
                {
                    "goods_name": x.goods_name,
                    "quantity": float(x.quantity),
                    "unit": x.unit or "件",
                    "batch_no": x.batch_no or "",
                }
            ],
        }
    slips = list(by_order.values())[:limit]
    for slip in slips:
        pid = slip.get("purchase_id")
        if pid:
            pp = db.query(Purchase).filter(Purchase.id == pid).first()
            slip["purchase_order_no"] = pp.order_no if pp else ""
    return slips


def _parse_range(range_key: str):
    """解析时间范围"""
    now = datetime.utcnow()
    if range_key == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range_key == "week":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range_key == "month":
        start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range_key == "year":
        start = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    # default week
    start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按角色返回工作台数据：统计卡片、预警、待办、临期、图表"""
    role = normalize_role(current_user.role or "counselor_teacher")

    # 通用统计（供 admin/procurement）
    goods_count = db.query(Goods).filter(Goods.is_active == True).count()
    purchase_count = db.query(Purchase).count()
    warning_pending = db.query(Warning).filter(Warning.status == "pending").count()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stock_in_today = (
        db.query(StockIn).filter(StockIn.created_at >= today_start).count() if hasattr(StockIn, "created_at") else 0
    )

    # 预警列表（最新 5 条）
    warnings = (
        db.query(Warning)
        .filter(Warning.status == "pending")
        .order_by(Warning.created_at.desc())
        .limit(5)
        .all()
    )
    warning_list = [
        {
            "id": w.id,
            "time": w.created_at.strftime("%H:%M") if w.created_at else "",
            "level": "high" if w.level == "high" else "medium" if w.level == "medium" else "low",
            "levelLabel": "紧急" if w.level == "high" else "关注" if w.level == "medium" else "提醒",
            "material": w.material,
            "desc": w.description or "",
        }
        for w in warnings
    ]

    # 临期库存（根据 produced_at + shelf_life_days 或简单按 quantity 筛选低库存）
    invs = db.query(Inventory).filter(Inventory.quantity > 0).limit(20).all()
    expiring_items = []
    for inv in invs:
        days_left = 999
        try:
            if inv.produced_at and inv.shelf_life_days:
                exp = inv.produced_at + timedelta(days=inv.shelf_life_days)
                exp_naive = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
                delta = exp_naive - datetime.utcnow()
                days_left = max(0, delta.days)
        except Exception:
            pass
        if days_left <= 30:
            expiring_items.append(
                {"name": inv.goods_name, "days": days_left, "count": int(inv.quantity)}
            )
    expiring_items = expiring_items[:5]
    if not expiring_items and invs:
        # 无明确临期则展示低库存
        for inv in invs[:5]:
            if inv.quantity < 50:
                expiring_items.append(
                    {"name": inv.goods_name, "days": 0, "count": int(inv.quantity)}
                )

    # 图表数据（按 range 聚合）
    chart_range = "week"
    start_dt, end_dt = _parse_range(chart_range)

    purchase_by_date = (
        db.query(func.date(Purchase.created_at).label("d"), func.count(Purchase.id).label("cnt"))
        .filter(Purchase.created_at >= start_dt, Purchase.created_at <= end_dt)
        .group_by(func.date(Purchase.created_at))
        .all()
    )
    stock_in_by_date = (
        db.query(func.date(StockIn.created_at).label("d"), func.count(StockIn.id).label("cnt"))
        .filter(StockIn.created_at >= start_dt, StockIn.created_at <= end_dt)
        .group_by(func.date(StockIn.created_at))
        .all()
    )
    stock_out_by_date = (
        db.query(func.date(StockOut.created_at).label("d"), func.count(StockOut.id).label("cnt"))
        .filter(StockOut.created_at >= start_dt, StockOut.created_at <= end_dt)
        .group_by(func.date(StockOut.created_at))
        .all()
    )

    days_in_range = (end_dt - start_dt).days or 7
    labels = []
    purchase_vals = []
    output_vals = []
    for i in range(days_in_range):
        d = (start_dt + timedelta(days=i)).date()
        labels.append(d.strftime("%m/%d"))
        p_cnt = next((x.cnt for x in purchase_by_date if str(x.d) == str(d)), 0)
        si_cnt = next((x.cnt for x in stock_in_by_date if str(x.d) == str(d)), 0)
        so_cnt = next((x.cnt for x in stock_out_by_date if str(x.d) == str(d)), 0)
        purchase_vals.append(p_cnt)
        output_vals.append(so_cnt)

    chart_data = {"x": labels, "purchase": purchase_vals, "output": output_vals}

    # 按角色返回不同结构
    if role == "counselor_teacher":
        pending = db.query(Purchase).filter(Purchase.applicant_id == current_user.id, Purchase.status == "pending").count()
        processing = db.query(Purchase).filter(Purchase.applicant_id == current_user.id, Purchase.status.in_(("approved", "confirmed", "stocked_in", "stocked_out", "delivering"))).count()
        pending_receive = db.query(Delivery).filter(Delivery.receiver_user_id == current_user.id, Delivery.status == "on_way").count()
        completed = db.query(Purchase).filter(Purchase.applicant_id == current_user.id, Purchase.status == "completed").count()

        todos = (
            db.query(Purchase)
            .filter(Purchase.applicant_id == current_user.id)
            .order_by(Purchase.created_at.desc())
            .limit(5)
            .all()
        )
        teacher_todos = [
            {
                "id": p.id,
                "time": (p.created_at.strftime("%m-%d") if p.created_at else ""),
                "status": p.status,
                "statusLabel": get_purchase_status_label(p.status),
                "title": p.order_no,
                "desc": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items)[:50],
            }
            for p in todos
        ]

        return {
            "stats": [
                {"title": "待审批", "value": pending, "trend": "down", "trendValue": "", "icon": "Document", "path": "/my-applications"},
                {"title": "处理中", "value": processing, "trend": "up", "trendValue": "", "icon": "Document", "path": "/my-applications"},
                {"title": "待确认收货", "value": pending_receive, "trend": "up", "trendValue": "", "icon": "Van", "path": "/my-applications"},
                {"title": "已完成", "value": completed, "trend": "up", "trendValue": "", "icon": "Document", "path": "/my-applications"},
            ],
            "warnings": [],
            "warningList": teacher_todos,
            "expiringItems": [],
            "chartData": chart_data,
            "shortcuts": [],
        }

    if role == "campus_supplier":
        sid = _resolve_supplier_id(db, current_user)
        pending = db.query(Purchase).filter(Purchase.supplier_id == sid, Purchase.status == "approved").count() if sid else 0
        shipped = db.query(Purchase).filter(Purchase.supplier_id == sid, Purchase.status.in_(("shipped", "stocked_in", "stocked_out", "delivering", "completed"))).count() if sid else 0

        orders = (
            db.query(Purchase)
            .filter(Purchase.supplier_id == sid, Purchase.status == "approved")
            .order_by(Purchase.created_at.desc())
            .limit(5)
            .all()
        ) if sid else []
        supplier_orders = [
            {
                "id": p.id,
                "time": (p.created_at.strftime("%H:%M") if p.created_at else ""),
                "title": p.order_no,
                "desc": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items)[:50],
            }
            for p in orders
        ]

        return {
            "stats": [
                {"title": "待接单", "value": pending, "trend": "down", "trendValue": "", "icon": "List", "path": "/supplier/orders"},
                {"title": "已发货", "value": shipped, "trend": "up", "trendValue": "", "icon": "List", "path": "/supplier/orders"},
            ],
            "warnings": [],
            "warningList": supplier_orders,
            "expiringItems": [],
            "chartData": chart_data,
            "shortcuts": [],
        }

    if role == "system_admin":
        user_count = db.query(User).count()
        supplier_count = db.query(Supplier).count()
        audit_count = db.query(AuditLog).count()
        sensitive_actions = [
            "purchase_reject",
            "supplier_confirm",
            "warning_handle",
            "purchase_admin_warn",
            "purchase_admin_penalty",
        ]
        sensitive_count = db.query(AuditLog).filter(AuditLog.action.in_(sensitive_actions)).count()
        ids_total = db.query(IDSEvent).count()
        ids_blocked = db.query(IDSEvent).filter(IDSEvent.blocked == 1).count()
        ids_today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ids_today = db.query(IDSEvent).filter(IDSEvent.created_at >= ids_today_start).count()
        latest_ids = (
            db.query(IDSEvent)
            .order_by(IDSEvent.created_at.desc())
            .limit(1)
            .first()
        )
        idsSecurity = {
            "total": ids_total,
            "blockedCount": ids_blocked,
            "todayCount": ids_today,
            "latest": {
                "client_ip": latest_ids.client_ip if latest_ids else "",
                "attack_type": latest_ids.attack_type if latest_ids else "",
                "created_at": latest_ids.created_at.strftime("%H:%M") if latest_ids and latest_ids.created_at else "",
            } if latest_ids else None,
        }
        return {
            "stats": [
                {"title": "用户总数", "value": user_count, "trend": "up", "trendValue": "", "icon": "User", "path": "/system/users"},
                {"title": "供应商总数", "value": supplier_count, "trend": "up", "trendValue": "", "icon": "OfficeBuilding", "path": "/supplier"},
                {"title": "审计日志", "value": audit_count, "trend": "up", "trendValue": "", "icon": "Document", "path": "/audit"},
                {"title": "敏感操作", "value": sensitive_count, "trend": "down", "trendValue": "待审查", "icon": "Warning", "path": "/audit"},
            ],
            "warnings": [],
            "warningList": [],
            "expiringItems": [],
            "chartData": {"x": [], "purchase": [], "output": []},
            "idsSecurity": idsSecurity,
        }

    if role == "warehouse_procurement":
        stock_out_today = (
            db.query(StockOut).filter(StockOut.created_at >= today_start).count() if hasattr(StockOut, "created_at") else 0
        )
        pending_stock_in = db.query(Purchase).filter(
            or_(and_(Purchase.status == "approved", Purchase.supplier_id == None), Purchase.status == "shipped")
        ).count()
        pending_stock_out = db.query(Purchase).filter(Purchase.status == "stocked_in").count()
        pending_delivery_create = db.query(Purchase).filter(Purchase.status == "stocked_out").count()
        stock_in_tasks = (
            db.query(Purchase)
            .filter(or_(and_(Purchase.status == "approved", Purchase.supplier_id == None), Purchase.status == "shipped"))
            .order_by(Purchase.created_at.desc())
            .limit(5)
            .all()
        )
        stock_out_tasks = (
            db.query(Purchase).filter(Purchase.status == "stocked_in").order_by(Purchase.created_at.desc()).limit(5).all()
        )
        delivery_create_tasks = (
            db.query(Purchase).filter(Purchase.status == "stocked_out").order_by(Purchase.created_at.desc()).limit(5).all()
        )
        handoff_tasks = []
        seen_ids = set()
        for p in stock_in_tasks + stock_out_tasks + delivery_create_tasks:
            if p.id in seen_ids:
                continue
            seen_ids.add(p.id)
            handoff_tasks.append({
                "id": p.id,
                "order_no": p.order_no,
                "status": p.status,
                "status_label": get_purchase_status_label(p.status),
                "receiver_name": p.receiver_name or "-",
                "destination": p.destination or "-",
                "handoff_code": p.handoff_code or "-",
            })
        return {
            "stats": [
                {"title": "物资种类", "value": goods_count, "trend": "up", "trendValue": "", "icon": "Box", "path": "/goods"},
                {"title": "库存条目", "value": db.query(Inventory).count(), "trend": "up", "trendValue": "", "icon": "Box", "path": "/stock/inventory"},
                {"title": "今日入库", "value": stock_in_today, "trend": "up", "trendValue": "", "icon": "Upload", "path": "/stock/in"},
                {"title": "今日出库", "value": stock_out_today, "trend": "up", "trendValue": "", "icon": "Download", "path": "/stock/out"},
            ],
            "warnings": [],
            "warningList": [],
            "expiringItems": expiring_items,
            "chartData": chart_data,
            "todayTodos": {
                "pendingStockIn": pending_stock_in,
                "pendingStockOut": pending_stock_out,
                "pendingDeliveryCreate": pending_delivery_create,
            },
            "handoffTasks": handoff_tasks[:8],
            "pendingOutboundDocuments": _pending_outbound_documents(db, 8),
            "recentOutboundSlips": _recent_outbound_slips(db, 8),
        }

    # logistics_admin：采购审批 + 态势感知，不做入库出库配送
    return {
        "stats": [
            {"title": "物资种类", "value": goods_count, "trend": "up", "trendValue": "", "icon": "Box", "path": "/goods"},
            {"title": "采购单数", "value": purchase_count, "trend": "up", "trendValue": "", "icon": "ShoppingCart", "path": "/purchase"},
            {"title": "待处理预警", "value": warning_pending, "trend": "down", "trendValue": "", "icon": "Warning", "path": "/warning"},
            {"title": "待审批", "value": db.query(Purchase).filter(Purchase.status == "pending").count(), "trend": "down", "trendValue": "", "icon": "Document", "path": "/purchase"},
        ],
        "warnings": warning_list,
        "warningList": warning_list,
        "expiringItems": expiring_items,
        "chartData": chart_data,
    }


_warehouse_screen = require_roles("warehouse_procurement")
_logistics_screen = require_roles("logistics_admin")


@router.get("/screen/warehouse")
def get_warehouse_screen(
    db: Session = Depends(get_db),
    current_user: User = Depends(_warehouse_screen),
):
    """仓储大屏：库存汇总、出入库趋势、预警、临期、配送"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt, end_dt = _parse_range("week")

    # 统计
    inv_total = db.query(Inventory).count()
    inv_qty_sum = db.query(func.sum(Inventory.quantity)).scalar() or 0
    stock_in_today = db.query(StockIn).filter(StockIn.created_at >= today_start).count()
    stock_out_today = db.query(StockOut).filter(StockOut.created_at >= today_start).count()
    warning_pending = db.query(Warning).filter(Warning.status == "pending").count()
    delivery_ongoing = db.query(Delivery).filter(Delivery.status.in_(("pending", "loading", "on_way"))).count()
    pending_stock_in = db.query(Purchase).filter(
        or_(and_(Purchase.status == "approved", Purchase.supplier_id == None), Purchase.status == "shipped")
    ).count()
    pending_stock_out = db.query(Purchase).filter(Purchase.status == "stocked_in").count()
    pending_delivery_create = db.query(Purchase).filter(Purchase.status == "stocked_out").count()
    waiting_receive = db.query(Delivery).filter(Delivery.status == "on_way").count()

    # 出入库趋势
    si_by_date = (
        db.query(func.date(StockIn.created_at).label("d"), func.count(StockIn.id).label("cnt"))
        .filter(StockIn.created_at >= start_dt, StockIn.created_at <= end_dt)
        .group_by(func.date(StockIn.created_at))
        .all()
    )
    so_by_date = (
        db.query(func.date(StockOut.created_at).label("d"), func.count(StockOut.id).label("cnt"))
        .filter(StockOut.created_at >= start_dt, StockOut.created_at <= end_dt)
        .group_by(func.date(StockOut.created_at))
        .all()
    )
    days_in_range = (end_dt - start_dt).days or 7
    labels = []
    in_vals = []
    out_vals = []
    for i in range(days_in_range):
        d = (start_dt + timedelta(days=i)).date()
        labels.append(d.strftime("%m/%d"))
        in_vals.append(next((x.cnt for x in si_by_date if str(x.d) == str(d)), 0))
        out_vals.append(next((x.cnt for x in so_by_date if str(x.d) == str(d)), 0))

    # 库存按物资汇总（前10）
    inv_by_goods = (
        db.query(Inventory.goods_name, func.sum(Inventory.quantity).label("total"))
        .group_by(Inventory.goods_name)
        .order_by(func.sum(Inventory.quantity).desc())
        .limit(10)
        .all()
    )
    inventory_top = [{"name": x.goods_name, "quantity": float(x.total or 0)} for x in inv_by_goods]

    # 预警、临期
    warnings = (
        db.query(Warning)
        .filter(Warning.status == "pending")
        .order_by(Warning.created_at.desc())
        .limit(10)
        .all()
    )
    warning_list = [
        {"id": w.id, "material": w.material, "level": w.level, "desc": w.description or ""}
        for w in warnings
    ]
    invs = db.query(Inventory).filter(Inventory.quantity > 0).limit(20).all()
    expiring = []
    for inv in invs:
        days_left = 999
        try:
            if inv.produced_at and inv.shelf_life_days:
                exp = inv.produced_at + timedelta(days=inv.shelf_life_days)
                exp_naive = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
                days_left = max(0, (exp_naive - datetime.utcnow()).days)
        except Exception:
            pass
        if days_left <= 30 or inv.quantity < 20:
            expiring.append({"name": inv.goods_name, "days": days_left, "count": int(inv.quantity)})
    expiring = expiring[:8]

    # 进行中配送
    deliveries = db.query(Delivery).filter(Delivery.status.in_(("pending", "loading", "on_way"))).limit(5).all()
    delivery_list = [
        {
            "id": d.id,
            "delivery_no": d.delivery_no,
            "destination": d.destination,
            "status": d.status,
            "status_label": get_delivery_status_label(d.status),
            "receiver_name": d.receiver_name or "-",
            "handoff_code": d.handoff_code or "-",
        }
        for d in deliveries
    ]
    stock_in_tasks = (
        db.query(Purchase)
        .filter(or_(
            and_(Purchase.status == "approved", Purchase.supplier_id == None),
            Purchase.status == "shipped",
        ))
        .order_by(Purchase.created_at.desc())
        .limit(6)
        .all()
    )
    stock_out_tasks = (
        db.query(Purchase)
        .filter(Purchase.status == "stocked_in")
        .order_by(Purchase.created_at.desc())
        .limit(6)
        .all()
    )
    delivery_create_tasks = (
        db.query(Purchase)
        .filter(Purchase.status == "stocked_out")
        .order_by(Purchase.created_at.desc())
        .limit(6)
        .all()
    )
    handoff_tasks = [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "receiver_name": p.receiver_name or "-",
            "destination": p.destination or "-",
            "handoff_code": p.handoff_code or "-",
            "summary": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items)[:60],
        }
        for p in (
            stock_in_tasks + [x for x in stock_out_tasks if x.id not in {p.id for p in stock_in_tasks}] + [x for x in delivery_create_tasks if x.id not in {p.id for p in stock_in_tasks + stock_out_tasks}]
        )[:8]
    ]

    return {
        "stats": {
            "inventoryTotal": inv_total,
            "inventoryQtySum": int(inv_qty_sum),
            "stockInToday": stock_in_today,
            "stockOutToday": stock_out_today,
            "warningPending": warning_pending,
            "deliveryOngoing": delivery_ongoing,
            "pendingStockIn": pending_stock_in,
            "pendingStockOut": pending_stock_out,
            "pendingDeliveryCreate": pending_delivery_create,
            "waitingReceive": waiting_receive,
        },
        "chart": {"labels": labels, "in": in_vals, "out": out_vals},
        "inventoryTop": inventory_top,
        "warnings": warning_list,
        "expiring": expiring,
        "deliveries": delivery_list,
        "handoffTasks": handoff_tasks,
        "pendingOutboundDocuments": _pending_outbound_documents(db, 8),
        "recentOutboundSlips": _recent_outbound_slips(db, 8),
    }


@router.get("/screen/logistics")
def get_logistics_screen(
    db: Session = Depends(get_db),
    current_user: User = Depends(_logistics_screen),
):
    """后勤大屏：采购流程、供应商、预警、配送"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt, end_dt = _parse_range("week")

    # 采购状态统计
    purchase_pending = db.query(Purchase).filter(Purchase.status == "pending").count()
    supplier_pending = db.query(Purchase).filter(Purchase.status == "approved").count()
    stock_pending = db.query(Purchase).filter(Purchase.status.in_(("confirmed", "shipped"))).count()
    dispatch_pending = db.query(Purchase).filter(Purchase.status.in_(("stocked_in", "stocked_out"))).count()
    receive_pending = db.query(Delivery).filter(Delivery.status == "on_way").count()
    purchase_completed = db.query(Purchase).filter(Purchase.status == "completed").count()
    supplier_count = db.query(Supplier).count()
    warning_pending = db.query(Warning).filter(Warning.status == "pending").count()
    delivery_ongoing = db.query(Delivery).filter(Delivery.status.in_(("pending", "loading", "on_way"))).count()

    # 采购趋势
    p_by_date = (
        db.query(func.date(Purchase.created_at).label("d"), func.count(Purchase.id).label("cnt"))
        .filter(Purchase.created_at >= start_dt, Purchase.created_at <= end_dt)
        .group_by(func.date(Purchase.created_at))
        .all()
    )
    days_in_range = (end_dt - start_dt).days or 7
    labels = []
    purchase_vals = []
    for i in range(days_in_range):
        d = (start_dt + timedelta(days=i)).date()
        labels.append(d.strftime("%m/%d"))
        purchase_vals.append(next((x.cnt for x in p_by_date if str(x.d) == str(d)), 0))

    # 近期闭环衔接（前10）
    handoff_rows = (
        db.query(Purchase)
        .filter(Purchase.status.in_(("pending", "approved", "confirmed", "shipped", "stocked_in", "stocked_out", "delivering", "completed")))
        .order_by(Purchase.created_at.desc())
        .limit(10)
        .all()
    )
    users_by_id = {u.id: u for u in db.query(User).all()}
    pending_purchases = [
        {
            "id": p.id,
            "order_no": p.order_no,
            "applicant": (u.real_name or u.username) if (u := users_by_id.get(p.applicant_id)) else "-",
            "summary": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items)[:60],
        }
        for p in db.query(Purchase).filter(Purchase.status == "pending").order_by(Purchase.created_at.desc()).limit(10).all()
    ]
    handoff_list = [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "handoff_code": p.handoff_code or "-",
            "receiver_name": p.receiver_name or "-",
            "destination": p.destination or "-",
        }
        for p in handoff_rows
    ]

    # 预警
    warnings = (
        db.query(Warning)
        .filter(Warning.status == "pending")
        .order_by(Warning.created_at.desc())
        .limit(10)
        .all()
    )
    warning_list = [
        {"id": w.id, "material": w.material, "level": w.level, "desc": w.description or ""}
        for w in warnings
    ]

    # 进行中配送
    deliveries = db.query(Delivery).filter(Delivery.status.in_(("pending", "loading", "on_way"))).limit(5).all()
    delivery_list = [
        {
            "id": d.id,
            "delivery_no": d.delivery_no,
            "destination": d.destination,
            "status": d.status,
            "receiver_name": d.receiver_name or "-",
            "handoff_code": d.handoff_code or "-",
        }
        for d in deliveries
    ]

    return {
        "stats": {
            "purchasePending": purchase_pending,
            "supplierPending": supplier_pending,
            "stockPending": stock_pending,
            "dispatchPending": dispatch_pending,
            "receivePending": receive_pending,
            "purchaseCompleted": purchase_completed,
            "supplierCount": supplier_count,
            "warningPending": warning_pending,
            "deliveryOngoing": delivery_ongoing,
        },
        "chart": {"labels": labels, "purchase": purchase_vals},
        "pendingPurchases": pending_purchases,
        "handoffList": handoff_list,
        "warnings": warning_list,
        "deliveries": delivery_list,
    }
