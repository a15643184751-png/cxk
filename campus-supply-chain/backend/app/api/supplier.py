from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.supplier import Supplier
from ..models.purchase import Purchase
from ..models.delivery import Delivery
from ..models.trace import TraceRecord
from ..models.user import User
from ..api.deps import get_current_user, has_role, require_roles
from ..services.audit import write_audit_log
from ..services.flow import append_trace, get_purchase_status_label, make_flow_code
from ..services.workflow import assert_transition

router = APIRouter(prefix="/supplier", tags=["supplier"])
_supplier_manager = require_roles("system_admin")  # 仅管理员可管理供应商
_supplier_list = require_roles("system_admin", "logistics_admin")  # 采购审批时需列出供应商分配


def _resolve_supplier_id(db: Session, current_user: User) -> int | None:
    """解析供应商 ID：用户绑定 > 首个可用供应商（预置兜底）"""
    sid = getattr(current_user, "supplier_id", None) or current_user.supplier_id
    if sid:
        return sid
    s = db.query(Supplier).filter(Supplier.is_blacklisted == False).order_by(Supplier.id.asc()).first()
    return s.id if s else None


@router.get("/orders")
def list_supplier_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """供应商：我的订单（分配给本公司的采购单）"""
    if not has_role(current_user, "campus_supplier"):
        return []
    sid = _resolve_supplier_id(db, current_user)
    q = db.query(Purchase).filter(Purchase.status.in_(["approved", "confirmed", "shipped", "stocked_in", "stocked_out", "delivering", "completed"]))
    if sid:
        q = q.filter(Purchase.supplier_id == sid)
    items = q.order_by(Purchase.created_at.desc()).limit(50).all()
    users_by_id = {u.id: u for u in db.query(User).all()}
    purchase_ids = [p.id for p in items]
    delivery_by_purchase: dict[int, str] = {}
    if purchase_ids:
        for d in db.query(Delivery).filter(Delivery.purchase_id.in_(purchase_ids)).all():
            if d.purchase_id:
                delivery_by_purchase[d.purchase_id] = d.delivery_no
    return [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "applicant": (users_by_id[p.applicant_id].real_name if p.applicant_id and p.applicant_id in users_by_id else "-"),
            "goods_summary": " ".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items),
            "created_at": p.created_at.strftime("%Y-%m-%d") if p.created_at else None,
            "handoff_code": p.handoff_code or "",
            "receiver_name": p.receiver_name or "",
            "destination": p.destination or "",
            "delivery_no": delivery_by_purchase.get(p.id) or "",
        }
        for p in items
    ]


@router.get("")
def list_suppliers(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_supplier_list),
):
    q = db.query(Supplier)
    if keyword:
        q = q.filter(Supplier.name.contains(keyword))
    return [{"id": s.id, "name": s.name, "contact": s.contact, "phone": s.phone, "address": s.address} for s in q.all()]


@router.put("/orders/{order_id}/confirm")
def confirm_supplier_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """供应商接单确认"""
    if not has_role(current_user, "campus_supplier"):
        raise HTTPException(status_code=403, detail="仅供应商可操作")
    sid = _resolve_supplier_id(db, current_user)
    if not sid:
        raise HTTPException(status_code=400, detail="系统未配置供应商，请联系管理员")
    p = db.query(Purchase).filter(Purchase.id == order_id, Purchase.supplier_id == sid).first()
    if not p:
        raise HTTPException(status_code=404, detail="订单不存在")
    assert_transition(p.status, {"approved"}, "供应商接单")
    p.status = "confirmed"  # 供应商已接单
    p.handoff_code = make_flow_code("HDS")
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="supplier_confirm",
        target_type="purchase",
        target_id=str(p.id),
        detail=f"供应商确认接单：{p.order_no}，交接码={p.handoff_code}",
    )
    append_trace(
        db,
        p.order_no,
        "供应商",
        f"供应商 {current_user.real_name or current_user.username} 已确认接单；当前状态={get_purchase_status_label(p.status)}；交接码={p.handoff_code}",
    )
    db.commit()
    return {"code": 200, "message": "接单成功", "order_no": p.order_no, "handoff_code": p.handoff_code}


@router.put("/orders/{order_id}/ship")
def ship_supplier_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """供应商发货/下发：接单后标记已发货，货发往仓储"""
    if not has_role(current_user, "campus_supplier"):
        raise HTTPException(status_code=403, detail="仅供应商可操作")
    sid = _resolve_supplier_id(db, current_user)
    if not sid:
        raise HTTPException(status_code=400, detail="系统未配置供应商，请联系管理员")
    p = db.query(Purchase).filter(Purchase.id == order_id, Purchase.supplier_id == sid).first()
    if not p:
        raise HTTPException(status_code=404, detail="订单不存在")
    assert_transition(p.status, {"confirmed"}, "供应商发货")
    p.status = "shipped"
    p.handoff_code = make_flow_code("HDX")
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="supplier_ship",
        target_type="purchase",
        target_id=str(p.id),
        detail=f"供应商发货：{p.order_no}，交接码={p.handoff_code}，货发往仓储",
    )
    append_trace(
        db,
        p.order_no,
        "供应商",
        f"供应商 {current_user.real_name or current_user.username} 已发货，交接码={p.handoff_code}；待仓储入库",
    )
    db.commit()
    return {"code": 200, "message": "发货成功", "order_no": p.order_no, "handoff_code": p.handoff_code}
