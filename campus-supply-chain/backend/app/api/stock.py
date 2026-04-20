from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.stock import StockIn, StockOut, Inventory
from ..models.purchase import Purchase
from ..models.goods import Goods
from ..models.warning import Warning
from ..models.trace import TraceRecord
from ..models.user import User
from ..api.deps import get_current_user, require_roles
from ..services.audit import write_audit_log
from ..services.flow import append_trace, get_purchase_status_label, make_flow_code
from ..services.workflow import assert_positive, assert_transition

router = APIRouter(prefix="/stock", tags=["stock"])
_stock_operator = require_roles("warehouse_procurement")
_stock_viewer = require_roles("system_admin", "logistics_admin", "warehouse_procurement")


class StockInItem(BaseModel):
    goods_name: str
    quantity: float
    unit: str = ""
    batch_no: str = ""


class StockInCreate(BaseModel):
    purchase_id: int | None = None  # 从采购单入库
    items: list[StockInItem] | None = None  # 或手工录入多条


class StockOutItem(BaseModel):
    goods_name: str
    quantity: float
    unit: str = ""
    batch_no: str | None = None


class StockOutCreate(BaseModel):
    purchase_id: int | None = None
    items: list[StockOutItem] | None = None


def _sync_inventory_add(db: Session, goods_name: str, quantity: float, unit: str, batch_no: str, category: str = ""):
    """入库时增加库存"""
    bn = batch_no or ""
    inv = db.query(Inventory).filter(Inventory.goods_name == goods_name, Inventory.batch_no == bn).first()
    if inv:
        inv.quantity += quantity
    else:
        db.add(Inventory(goods_name=goods_name, category=category, quantity=quantity, unit=unit or "件", batch_no=bn))


def _is_expired(inv: Inventory) -> bool:
    if not inv.produced_at or not inv.shelf_life_days:
        return False
    return inv.produced_at + timedelta(days=inv.shelf_life_days) < datetime.now(inv.produced_at.tzinfo)


def _sync_inventory_sub(db: Session, goods_name: str, quantity: float):
    """出库时减少库存并返回扣减批次；库存不足/全过期时返回失败原因。"""
    invs = (
        db.query(Inventory)
        .filter(Inventory.goods_name == goods_name, Inventory.quantity > 0)
        .order_by(Inventory.produced_at.asc(), Inventory.id.asc())
        .all()
    )
    valid_invs = [inv for inv in invs if not _is_expired(inv)]
    expired_total = sum(inv.quantity for inv in invs if _is_expired(inv))
    total_valid = sum(inv.quantity for inv in valid_invs)
    if total_valid < quantity:
        if expired_total > 0 and total_valid == 0:
            return {"ok": False, "detail": f"{goods_name} 仅剩过期库存，禁止出库", "allocations": []}
        return {"ok": False, "detail": f"{goods_name} 可用库存不足", "allocations": []}

    remaining = quantity
    allocations: list[dict] = []
    for inv in valid_invs:
        if remaining <= 0:
            break
        deduct = min(inv.quantity, remaining)
        inv.quantity -= deduct
        remaining -= deduct
        allocations.append({"batch_no": inv.batch_no or "", "quantity": deduct, "unit": inv.unit or "件"})
    return {"ok": True, "detail": "", "allocations": allocations}


def _upsert_low_stock_warning(db: Session, goods_name: str):
    """库存变化后自动感知：低库存则创建/更新预警，恢复则关闭预警。"""
    total = db.query(func.sum(Inventory.quantity)).filter(Inventory.goods_name == goods_name).scalar() or 0
    g = db.query(Goods).filter(Goods.name == goods_name).first()
    safe_qty = 20 if g and (g.safety_level in ("critical", "high")) else 10
    material = goods_name
    pending = db.query(Warning).filter(Warning.status == "pending", Warning.material == material).first()
    if total < safe_qty:
        level = "high" if total <= max(2, safe_qty * 0.3) else "medium"
        desc = f"库存仅 {total}{(g.unit if g else '') or '件'}，低于安全线 {safe_qty}{(g.unit if g else '') or '件'}，建议补货"
        if pending:
            pending.level = level
            pending.description = desc
        else:
            db.add(Warning(level=level, material=material, description=desc, status="pending"))
    else:
        if pending:
            pending.status = "handled"


@router.post("/in")
def create_stock_in(
    req: StockInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_stock_operator),
):
    """采购入库：支持从采购单入库或手工录入"""
    items_to_in = []
    purchase_id = req.purchase_id
    purchase_order_no = ""

    if purchase_id:
        p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if not p:
            raise HTTPException(status_code=400, detail="采购单不存在")
        if p.supplier_id:
            assert_transition(p.status, {"shipped"}, "采购入库")
        else:
            assert_transition(p.status, {"approved"}, "采购入库")
        for it in p.items:
            assert_positive(it.quantity, "入库数量")
            items_to_in.append(
                {
                    "goods_name": it.goods_name,
                    "quantity": it.quantity,
                    "unit": it.unit or "件",
                    "batch_no": make_flow_code("BAT"),
                }
            )
        purchase_order_no = p.order_no
    elif req.items:
        for it in req.items:
            assert_positive(it.quantity, "入库数量")
            items_to_in.append({"goods_name": it.goods_name, "quantity": it.quantity, "unit": it.unit or "件", "batch_no": it.batch_no or ""})
    else:
        raise HTTPException(status_code=400, detail="请选择采购单或填写入库明细")

    order_no = f"IN{datetime.now().strftime('%Y%m%d%H%M%S')}"
    for item in items_to_in:
        sin = StockIn(
            order_no=order_no,
            goods_name=item["goods_name"],
            quantity=item["quantity"],
            unit=item["unit"],
            batch_no=item["batch_no"],
            purchase_id=purchase_id,
        )
        db.add(sin)
        db.flush()
        _sync_inventory_add(db, item["goods_name"], item["quantity"], item["unit"], item["batch_no"])
        _upsert_low_stock_warning(db, item["goods_name"])
        if item["batch_no"]:
            append_trace(
                db,
                item["batch_no"],
                "入库",
                f"入库单 {order_no}，{item['goods_name']} {item['quantity']}{item['unit']}",
            )
        if purchase_id:
            append_trace(
                db,
                purchase_order_no,
                "入库",
                f"入库单 {order_no}，{item['goods_name']} {item['quantity']}{item['unit']}",
            )

    if purchase_id:
        p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
        if p:
            p.status = "stocked_in"
            p.handoff_code = make_flow_code("HDI")
            write_audit_log(
                db,
                user_id=current_user.id,
                user_name=current_user.real_name or current_user.username,
                user_role=current_user.role,
                action="stock_in",
                target_type="purchase",
                target_id=str(p.id),
                detail=f"采购单 {p.order_no} 入库完成，入库单号={order_no}，交接码={p.handoff_code}",
            )
            append_trace(
                db,
                p.order_no,
                "入库",
                f"仓储完成入库，入库单号={order_no}；当前状态={get_purchase_status_label(p.status)}；下一环待出库；交接码={p.handoff_code}",
            )
    else:
        write_audit_log(
            db,
            user_id=current_user.id,
            user_name=current_user.real_name or current_user.username,
            user_role=current_user.role,
            action="stock_in_manual",
            target_type="stock_in",
            target_id=order_no,
            detail=f"手工入库单 {order_no}，条目数={len(items_to_in)}",
        )

    db.commit()
    return {"code": 200, "message": "入库成功", "order_no": order_no}


@router.post("/out")
def create_stock_out(
    req: StockOutCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_stock_operator),
):
    """领用出库"""
    if not req.purchase_id and not req.items:
        raise HTTPException(status_code=400, detail="请填写出库明细")

    order_no = f"OUT{datetime.now().strftime('%Y%m%d%H%M%S')}"
    purchase = None
    items_to_out = req.items
    receiver_name = ""
    destination = ""
    handoff_code = ""

    if req.purchase_id:
        purchase = db.query(Purchase).filter(Purchase.id == req.purchase_id).first()
        if not purchase:
            raise HTTPException(status_code=404, detail="关联采购单不存在")
        assert_transition(purchase.status, {"stocked_in"}, "按申请出库")
        items_to_out = [
            StockOutItem(goods_name=it.goods_name, quantity=it.quantity, unit=it.unit or "件")
            for it in purchase.items
        ]
        receiver_name = purchase.receiver_name or ""
        destination = purchase.destination or ""
        handoff_code = make_flow_code("HDO")

    for it in items_to_out:
        assert_positive(it.quantity, "出库数量")
        result = _sync_inventory_sub(db, it.goods_name, it.quantity)
        if not result["ok"]:
            raise HTTPException(status_code=400, detail=result["detail"])
        db.add(StockOut(
            order_no=order_no,
            goods_name=it.goods_name,
            quantity=it.quantity,
            unit=it.unit or "件",
            batch_no=it.batch_no or "",
            purchase_id=(purchase.id if purchase else None),
            destination=destination,
            receiver_name=receiver_name,
            handoff_code=handoff_code,
        ))
        for batch in result["allocations"]:
            if batch["batch_no"]:
                append_trace(
                    db,
                    batch["batch_no"],
                    "出库",
                    f"出库单 {order_no}，{it.goods_name} {batch['quantity']}{batch['unit']}",
                )
        _upsert_low_stock_warning(db, it.goods_name)
        if purchase:
            append_trace(
                db,
                purchase.order_no,
                "出库",
                f"按申请单出库，出库单号={order_no}；物资={it.goods_name} {it.quantity}{it.unit or '件'}；目的地={destination or '-'}；收货人={receiver_name or '-'}；交接码={handoff_code}",
            )

    if purchase:
        purchase.status = "stocked_out"
        purchase.handoff_code = handoff_code
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="stock_out",
        target_type="stock_out",
        target_id=order_no,
        detail=f"出库单 {order_no}，条目数={len(items_to_out)}{'，关联申请单=' + purchase.order_no if purchase else ''}{'，交接码=' + handoff_code if handoff_code else ''}",
    )
    db.commit()
    return {"code": 200, "message": "出库成功", "order_no": order_no, "handoff_code": handoff_code}


@router.get("/in")
def list_stock_in(
    db: Session = Depends(get_db),
    current_user: User = Depends(_stock_viewer),
):
    items = db.query(StockIn).order_by(StockIn.created_at.desc()).limit(200).all()
    return [{"id": x.id, "order_no": x.order_no, "goods_name": x.goods_name, "quantity": x.quantity, "unit": x.unit, "batch_no": x.batch_no or "", "purchase_id": x.purchase_id, "created_at": x.created_at.isoformat() if x.created_at else None} for x in items]


@router.get("/out")
def list_stock_out(
    db: Session = Depends(get_db),
    current_user: User = Depends(_stock_viewer),
):
    items = db.query(StockOut).order_by(StockOut.created_at.desc()).limit(200).all()
    return [
        {
            "id": x.id,
            "order_no": x.order_no,
            "goods_name": x.goods_name,
            "quantity": x.quantity,
            "unit": x.unit,
            "batch_no": x.batch_no,
            "purchase_id": x.purchase_id,
            "destination": x.destination or "",
            "receiver_name": x.receiver_name or "",
            "handoff_code": x.handoff_code or "",
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in items
    ]


@router.get("/inventory")
def list_inventory(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_stock_viewer),
):
    q = db.query(Inventory)
    if keyword:
        q = q.filter(Inventory.goods_name.contains(keyword))
    items = q.all()
    goods_map = {g.name: g for g in db.query(Goods).all()}
    now = datetime.utcnow()

    result = []
    for x in items:
        g = goods_map.get(x.goods_name)
        safe_qty = 20 if g and (g.safety_level in ("critical", "high")) else 10
        is_low_stock = float(x.quantity or 0) < safe_qty

        days_to_expire = None
        if x.produced_at and x.shelf_life_days:
            expire_at = x.produced_at + timedelta(days=x.shelf_life_days)
            expire_naive = (
                expire_at.replace(tzinfo=None)
                if getattr(expire_at, "tzinfo", None)
                else expire_at
            )
            days_to_expire = (expire_naive - now).days

        result.append(
            {
                "id": x.id,
                "goods_name": x.goods_name,
                "category": x.category,
                "quantity": x.quantity,
                "unit": x.unit,
                "batch_no": x.batch_no,
                "safe_qty": safe_qty,
                "is_low_stock": is_low_stock,
                "days_to_expire": days_to_expire,
                "updated_at": x.updated_at.isoformat() if x.updated_at else None,
            }
        )

    return result
