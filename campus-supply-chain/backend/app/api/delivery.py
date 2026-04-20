from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.delivery import Delivery
from ..models.stock import StockOut
from ..models.purchase import Purchase
from ..models.user import User
from ..api.deps import get_current_user, require_roles
from ..services.audit import write_audit_log
from ..services.flow import append_trace, get_delivery_status_label, make_flow_code
from ..services.workflow import assert_transition

router = APIRouter(prefix="/delivery", tags=["delivery"])
_delivery_operator = require_roles("logistics_admin", "warehouse_procurement")
_delivery_viewer = require_roles("system_admin", "logistics_admin", "warehouse_procurement")
_teacher_receiver = require_roles("counselor_teacher")


class DeliveryCreateRequest(BaseModel):
    stock_out_id: int | None = None
    purchase_id: int | None = None  # 二选一：按采购单创建时自动关联出库单
    destination: str = ""
    receiver_name: str = ""
    remark: str = ""


class DeliveryStatusRequest(BaseModel):
    status: str
    remark: str = ""


class DeliveryReceiveRequest(BaseModel):
    remark: str = ""


@router.get("")
def list_deliveries(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_delivery_viewer),
):
    q = db.query(Delivery).order_by(Delivery.created_at.desc())
    if status:
        q = q.filter(Delivery.status == status)
    items = q.limit(50).all()
    purchases = {
        p.id: p
        for p in db.query(Purchase).filter(Purchase.id.in_([x.purchase_id for x in items if x.purchase_id])).all()
    } if items else {}
    return [
        {
            "id": x.id,
            "delivery_no": x.delivery_no,
            "purchase_id": x.purchase_id,
            "purchase_order_no": (purchases[x.purchase_id].order_no if x.purchase_id in purchases else ""),
            "destination": x.destination,
            "status": x.status,
            "status_label": get_delivery_status_label(x.status),
            "receiver_name": x.receiver_name or "",
            "handoff_code": x.handoff_code or "",
            "scheduled_at": x.scheduled_at.isoformat() if x.scheduled_at else None,
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in items
    ]


@router.get("/my")
def list_my_deliveries(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_receiver),
):
    q = db.query(Delivery).filter(Delivery.receiver_user_id == current_user.id).order_by(Delivery.created_at.desc())
    if status:
        q = q.filter(Delivery.status == status)
    items = q.limit(50).all()
    purchases = {
        p.id: p
        for p in db.query(Purchase).filter(Purchase.id.in_([x.purchase_id for x in items if x.purchase_id])).all()
    } if items else {}
    return [
        {
            "id": x.id,
            "delivery_no": x.delivery_no,
            "purchase_order_no": (purchases[x.purchase_id].order_no if x.purchase_id in purchases else ""),
            "destination": x.destination,
            "status": x.status,
            "status_label": get_delivery_status_label(x.status),
            "receiver_name": x.receiver_name or "",
            "handoff_code": x.handoff_code or "",
            "created_at": x.created_at.isoformat() if x.created_at else None,
            "can_confirm_receive": x.status == "on_way",
        }
        for x in items
    ]


@router.post("")
def create_delivery(
    req: DeliveryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_delivery_operator),
):
    stock_out = None
    purchase = None
    if req.stock_out_id:
        stock_out = db.query(StockOut).filter(StockOut.id == req.stock_out_id).first()
        if not stock_out:
            raise HTTPException(status_code=404, detail="关联出库记录不存在")
        if stock_out.purchase_id:
            purchase = db.query(Purchase).filter(Purchase.id == stock_out.purchase_id).first()
    elif req.purchase_id:
        purchase = db.query(Purchase).filter(Purchase.id == req.purchase_id).first()
        if not purchase:
            raise HTTPException(status_code=404, detail="采购单不存在")
        stock_out = db.query(StockOut).filter(StockOut.purchase_id == purchase.id).order_by(StockOut.id.desc()).first()
        if not stock_out:
            raise HTTPException(status_code=400, detail="该采购单暂无出库记录，请先完成出库")
    if purchase:
        assert_transition(purchase.status, {"stocked_out"}, "创建配送")
        existing_open = (
            db.query(Delivery)
            .filter(Delivery.purchase_id == purchase.id, Delivery.status.in_(("pending", "loading", "on_way")))
            .first()
        )
        if existing_open:
            raise HTTPException(status_code=400, detail=f"该申请已存在进行中配送单：{existing_open.delivery_no}")
    destination = (req.destination or "").strip() or (stock_out.destination if stock_out else "") or (purchase.destination if purchase else "") or ""
    if not destination:
        raise HTTPException(status_code=400, detail="配送目的地不能为空")
    delivery_no = f"DL{datetime.now().strftime('%Y%m%d%H%M%S')}"
    d = Delivery(
        delivery_no=delivery_no,
        stock_out_id=(stock_out.id if stock_out else req.stock_out_id),
        purchase_id=(purchase.id if purchase else None),
        receiver_user_id=(purchase.applicant_id if purchase else None),
        destination=destination,
        status="pending",
        receiver_name=(req.receiver_name.strip() if req.receiver_name else "") or (stock_out.receiver_name if stock_out else "") or (purchase.receiver_name if purchase else ""),
        handoff_code=(stock_out.handoff_code if stock_out and stock_out.handoff_code else make_flow_code("HDD")),
        remark=req.remark.strip(),
    )
    db.add(d)
    if purchase:
        purchase.status = "delivering"
        purchase.handoff_code = d.handoff_code
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="delivery_create",
        target_type="delivery",
        target_id=delivery_no,
        detail=f"创建配送单，目的地={d.destination}，关联出库ID={req.stock_out_id or '-'}，交接码={d.handoff_code}",
    )
    if stock_out and stock_out.batch_no:
        append_trace(
            db,
            stock_out.batch_no,
            "配送",
            f"创建配送单 {delivery_no}，目的地={d.destination}",
        )
    if purchase:
        append_trace(
            db,
            purchase.order_no,
            "配送",
            f"创建配送单 {delivery_no}；目的地={d.destination}；收货人={d.receiver_name or '-'}；当前状态=配送中待签收；交接码={d.handoff_code}",
        )
    db.commit()
    return {"code": 200, "message": "配送单已创建", "delivery_no": delivery_no, "handoff_code": d.handoff_code}


@router.put("/{delivery_id}/status")
def update_delivery_status(
    delivery_id: int,
    req: DeliveryStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_delivery_operator),
):
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="配送单不存在")

    # pending -> loading -> on_way，签收由教师确认
    target = (req.status or "").strip()
    transition_map = {
        "loading": {"pending"},
        "on_way": {"loading"},
    }
    if target not in transition_map:
        raise HTTPException(status_code=400, detail="非法配送状态")
    assert_transition(d.status, transition_map[target], f"配送状态更新为 {target}")

    d.status = target
    if req.remark:
        d.remark = (d.remark + "\n" + req.remark).strip() if d.remark else req.remark.strip()
    if target == "received":
        d.actual_at = datetime.now()

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="delivery_status_update",
        target_type="delivery",
        target_id=d.delivery_no,
        detail=f"配送状态更新为 {target}",
    )
    if d.stock_out_id:
        stock_out = db.query(StockOut).filter(StockOut.id == d.stock_out_id).first()
        if stock_out and stock_out.batch_no:
            append_trace(
                db,
                stock_out.batch_no,
                "配送",
                f"配送单 {d.delivery_no} 状态更新：{get_delivery_status_label(target)}",
            )
    if d.purchase_id:
        purchase = db.query(Purchase).filter(Purchase.id == d.purchase_id).first()
        if purchase:
            append_trace(
                db,
                purchase.order_no,
                "配送",
                f"配送单 {d.delivery_no} 状态更新：{get_delivery_status_label(target)}",
            )
    db.commit()
    return {"code": 200, "message": "配送状态已更新", "status": d.status}


@router.put("/{delivery_id}/receive")
def confirm_delivery_receive(
    delivery_id: int,
    req: DeliveryReceiveRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_teacher_receiver),
):
    d = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="配送单不存在")
    if d.receiver_user_id and d.receiver_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="仅收货人可确认签收")
    assert_transition(d.status, {"on_way"}, "确认收货")

    d.status = "received"
    d.actual_at = datetime.now()
    d.confirmed_at = d.actual_at
    d.confirmed_by_id = current_user.id
    d.sign_remark = (req.remark if req else "") or ""

    purchase = db.query(Purchase).filter(Purchase.id == d.purchase_id).first() if d.purchase_id else None
    if purchase:
        purchase.status = "completed"
        purchase.completed_at = d.actual_at
        purchase.handoff_code = make_flow_code("HDR")

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="delivery_receive_confirm",
        target_type="delivery",
        target_id=d.delivery_no,
        detail=f"教师确认收货，配送单={d.delivery_no}，签收备注={d.sign_remark or '-'}",
    )
    if purchase:
        append_trace(
            db,
            purchase.order_no,
            "签收",
            f"收货人 {current_user.real_name or current_user.username} 已确认签收；配送单={d.delivery_no}；闭环完成；交接码={purchase.handoff_code}",
        )
    db.commit()
    return {"code": 200, "message": "确认收货成功", "status": d.status}
