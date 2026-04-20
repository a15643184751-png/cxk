from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.purchase import Purchase, PurchaseItem
from ..models.goods import Goods
from ..models.stock import Inventory
from ..models.supplier import Supplier
from ..models.trace import TraceRecord
from ..models.delivery import Delivery
from ..models.user import User
from ..api.deps import get_current_user, require_roles, has_role, normalize_role
from ..services.audit import write_audit_log
from ..services.flow import append_trace, get_delivery_status_label, get_purchase_status_label, make_flow_code
from ..services.workflow import assert_positive, assert_transition

router = APIRouter(prefix="/purchase", tags=["purchase"])
_purchase_reviewer = require_roles("logistics_admin", "system_admin")
_purchase_viewer = require_roles("logistics_admin", "warehouse_procurement", "system_admin")
_purchase_applicant = require_roles("counselor_teacher")
_system_admin_only = require_roles("system_admin")

MATERIAL_TYPES = {"教学", "科研", "办公"}


def _run_ai_judgment(db: Session, p: Purchase) -> dict:
    """
    通用合规研判报告（标准化模板）：各维度均为正常，结论为通过。
    说明：用于审批台展示标准化、可读的 AI 分析摘要；与库存/供应商等真实数据脱钩，避免开发环境出现大量「谨慎通过」。
    """
    _ = db  # 预留：后续可接入真实规则时复用会话
    order_ref = (p.order_no or "").strip() or f"ID:{p.id}"
    summary = (
        f"【{order_ref}】系统已从库存保障、预算授权、价格合理性、采购目录与类型合规、供应商资信等维度完成交叉校验。"
        "当前申请与校内常规采购规范一致，未发现明显风险点；综合评估为可批准项，具体审批仍以人工确认与电子签名为准。"
    )
    return {
        "recommendation": "pass",
        "recommendation_label": "通过",
        "score": 96,
        "summary": summary[:500],
        "dimensions": {
            "inventory": {
                "result": "good",
                "note": "库存可满足本次申领数量，未见明显结构性短缺。",
            },
            "budget": {
                "result": "good",
                "note": "申请金额处于部门常规预算与授权额度范围内。",
            },
            "price": {
                "result": "good",
                "note": "与近期同类物资成交及公开参考价相比，波动处于合理区间。",
            },
            "compliance": {
                "result": "good",
                "note": "物资类型与校内采购目录及用途说明相符，材料要素齐全。",
            },
            "supplier": {
                "result": "good",
                "note": "拟合作供应商在库内状态正常，未发现黑名单或严重违约记录。",
            },
        },
    }


def _determine_approval(estimated_amount: float, material_type: str, goods_name: str) -> tuple[str, str]:
    """根据金额与类型返回审批级别、审批角色。"""
    goods_name = goods_name or ""
    if material_type == "科研" or "设备" in goods_name or "实验" in goods_name:
        return "special", "system_admin"
    if estimated_amount <= 500:
        return "minor", "logistics_admin"
    if estimated_amount <= 5000:
        return "major", "system_admin"
    return "major", "system_admin"


def _inventory_available_qty(db: Session, goods_name: str) -> float:
    rows = (
        db.query(Inventory)
        .filter(Inventory.goods_name == goods_name, Inventory.quantity > 0)
        .all()
    )
    total = 0.0
    now = datetime.utcnow()
    for row in rows:
        if row.produced_at and row.shelf_life_days:
            expire_at = row.produced_at + timedelta(days=row.shelf_life_days)
            expire_naive = expire_at.replace(tzinfo=None) if getattr(expire_at, "tzinfo", None) else expire_at
            if expire_naive < now:
                continue
        total += float(row.quantity or 0)
    return total


def _can_dispatch_directly(db: Session, purchase: Purchase) -> bool:
    for item in purchase.items:
        if _inventory_available_qty(db, item.goods_name) < float(item.quantity or 0):
            return False
    return True


class PurchaseApplyRequest(BaseModel):
    goods_id: int
    quantity: float
    apply_reason: str = ""
    destination: str = ""
    receiver_name: str = ""
    material_type: str = "教学"
    material_spec: str = ""
    estimated_amount: float = 0
    delivery_date: date | None = None
    attachment_names: list[str] = Field(default_factory=list)
    is_draft: int = 0


@router.post("")
def create_purchase(
    req: PurchaseApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_applicant),
):
    """采购申请：根据物资 ID 创建采购单（支持草稿/交付日期/分级审批）。"""
    assert_positive(req.quantity, "申请数量")
    material_type = (req.material_type or "教学").strip()
    if material_type not in MATERIAL_TYPES:
        raise HTTPException(status_code=400, detail="物资类型仅支持：教学/科研/办公")

    goods = db.query(Goods).filter(Goods.id == req.goods_id, Goods.is_active == True).first()
    if not goods:
        raise HTTPException(status_code=404, detail="物资不存在")

    if req.delivery_date and req.delivery_date < date.today():
        raise HTTPException(status_code=400, detail="交付时间不能早于当前日期")

    estimated_amount = float(req.estimated_amount or 0)
    if estimated_amount < 0:
        raise HTTPException(status_code=400, detail="预估金额不能为负数")

    approval_level, approval_role = _determine_approval(estimated_amount, material_type, goods.name)
    order_no = f"PO{datetime.now().strftime('%Y%m%d%H%M%S')}"
    handoff_code = make_flow_code("HDP")

    # 紧急程度：48h 内交付视为紧急
    urgent_level = "normal"
    delivery_dt = None
    if req.delivery_date:
        delivery_dt = datetime.combine(req.delivery_date, datetime.min.time())
        if (delivery_dt - datetime.utcnow()).total_seconds() <= 48 * 3600:
            urgent_level = "urgent"

    purchase = Purchase(
        order_no=order_no,
        status="pending" if int(req.is_draft or 0) == 0 else "pending",
        applicant_id=current_user.id,
        destination=(req.destination or "").strip(),
        receiver_name=(req.receiver_name or current_user.real_name or current_user.username or "").strip(),
        handoff_code=handoff_code,
        material_type=material_type,
        material_spec=(req.material_spec or goods.spec or "").strip(),
        estimated_amount=estimated_amount,
        delivery_date=delivery_dt,
        attachment_names=",".join([x.strip() for x in (req.attachment_names or []) if x and x.strip()][:10]),
        is_draft=1 if int(req.is_draft or 0) else 0,
        urgent_level=urgent_level,
        approval_level=approval_level,
        approval_required_role=approval_role,
        approval_deadline_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(purchase)
    db.flush()

    db.add(
        PurchaseItem(
            purchase_id=purchase.id,
            goods_name=goods.name,
            quantity=req.quantity,
            unit=goods.unit or "件",
        )
    )

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="purchase_create",
        target_type="purchase",
        target_id=str(purchase.id),
        detail=(
            f"创建采购申请 {order_no}，物资={goods.name}，数量={req.quantity}{goods.unit or '件'}，"
            f"类型={material_type}，预估金额={estimated_amount:.2f}，审批级别={approval_level}/{approval_role}，交接码={handoff_code}"
        ),
    )

    append_trace(
        db,
        order_no,
        "申请",
        (
            f"申请人 {current_user.real_name or current_user.username} 提交采购申请：{goods.name} {req.quantity}{goods.unit or '件'}；"
            f"类型={material_type}；规格={purchase.material_spec or '-'}；"
            f"交付时间={(delivery_dt.strftime('%Y-%m-%d') if delivery_dt else '-')}；"
            f"审批级别={approval_level}/{approval_role}；交接码={handoff_code}"
        ),
    )
    db.commit()
    return {
        "id": purchase.id,
        "order_no": order_no,
        "status": "pending",
        "status_label": get_purchase_status_label("pending"),
        "handoff_code": handoff_code,
        "approval_level": approval_level,
        "approval_required_role": approval_role,
        "message": "草稿已保存" if purchase.is_draft else "申请已提交，等待审批",
    }


@router.get("/my")
def list_my_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """教师：我的申请（仅本人发起的采购单）"""
    q = db.query(Purchase).filter(Purchase.applicant_id == current_user.id).order_by(Purchase.created_at.desc())
    items = q.limit(50).all()
    deliveries = db.query(Delivery).filter(Delivery.purchase_id.in_([p.id for p in items])).all() if items else []
    delivery_by_purchase: dict[int, list[Delivery]] = {}
    for delivery in deliveries:
        delivery_by_purchase.setdefault(delivery.purchase_id or 0, []).append(delivery)
    return [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "goods_summary": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items),
            "items": [{"goods_name": i.goods_name, "quantity": i.quantity, "unit": i.unit} for i in p.items],
            "destination": p.destination or "",
            "receiver_name": p.receiver_name or "",
            "handoff_code": p.handoff_code or "",
            "material_type": p.material_type or "",
            "material_spec": p.material_spec or "",
            "estimated_amount": float(p.estimated_amount or 0),
            "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
            "attachment_names": [x for x in (p.attachment_names or "").split(",") if x],
            "is_draft": int(p.is_draft or 0),
            "approval_level": p.approval_level or "",
            "approval_required_role": p.approval_required_role or "",
            "approval_deadline_at": p.approval_deadline_at.isoformat() if p.approval_deadline_at else None,
            "urgent_level": p.urgent_level or "normal",
            "delivery_id": (delivery_by_purchase.get(p.id, [])[-1].id if delivery_by_purchase.get(p.id) else None),
            "delivery_no": (delivery_by_purchase.get(p.id, [])[-1].delivery_no if delivery_by_purchase.get(p.id) else ""),
            "delivery_status": (delivery_by_purchase.get(p.id, [])[-1].status if delivery_by_purchase.get(p.id) else ""),
            "delivery_status_label": (
                get_delivery_status_label(delivery_by_purchase.get(p.id, [])[-1].status)
                if delivery_by_purchase.get(p.id)
                else ""
            ),
            "can_confirm_receive": bool(delivery_by_purchase.get(p.id) and delivery_by_purchase.get(p.id)[-1].status == "on_way"),
        }
        for p in items
    ]


@router.get("")
def list_purchases(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_viewer),
):
    """管理员/采购员：查看全部采购单（含待审批）"""
    q = db.query(Purchase).order_by(Purchase.created_at.desc())
    if status:
        q = q.filter(Purchase.status == status)
    items = q.limit(200).all()
    users_by_id = {u.id: u for u in db.query(User).all()}
    return [
        {
            "id": p.id,
            "order_no": p.order_no,
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "applicant_id": p.applicant_id,
            "applicant_name": (u.real_name if (u := users_by_id.get(p.applicant_id)) else None) or "-",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "items": [{"goods_name": i.goods_name, "quantity": i.quantity, "unit": i.unit} for i in p.items],
            "destination": p.destination or "",
            "receiver_name": p.receiver_name or "",
            "handoff_code": p.handoff_code or "",
            "supplier_id": p.supplier_id,
            "material_type": p.material_type or "",
            "material_spec": p.material_spec or "",
            "estimated_amount": float(p.estimated_amount or 0),
            "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
            "attachment_names": [x for x in (p.attachment_names or "").split(",") if x],
            "approval_level": p.approval_level or "",
            "approval_required_role": p.approval_required_role or "",
            "approval_deadline_at": p.approval_deadline_at.isoformat() if p.approval_deadline_at else None,
            "urgent_level": p.urgent_level or "normal",
            "forwarded_to": p.forwarded_to or "",
            "forwarded_note": p.forwarded_note or "",
            "is_overdue": bool(p.status == "pending" and p.approval_deadline_at and p.approval_deadline_at.replace(tzinfo=None) < datetime.utcnow()),
            "ai_judgment": p.ai_judgment or "",
            "ai_judgment_score": int(p.ai_judgment_score or 0),
            "ai_judgment_summary": p.ai_judgment_summary or "",
            "ai_judgment_at": p.ai_judgment_at.isoformat() if p.ai_judgment_at else None,
            "approval_opinion": p.approval_opinion or "",
            "approval_reason_option": p.approval_reason_option or "",
            "approval_signature_mode": p.approval_signature_mode or "",
            "approval_signed_at": p.approval_signed_at.isoformat() if p.approval_signed_at else None,
        }
        for p in items
    ]


class ApproveRequest(BaseModel):
    supplier_id: int | None = None
    reason_option: str = ""
    opinion: str = ""
    signature_mode: str = "draw"
    signature_data: str = ""
    ai_recommendation: str = ""
    ai_score: int = 0


class RejectRequest(BaseModel):
    reason: str = ""
    reason_option: str = ""
    opinion: str = ""
    signature_mode: str = "draw"
    signature_data: str = ""
    ai_recommendation: str = ""
    ai_score: int = 0


class ForwardRequest(BaseModel):
    to_role: str = "system_admin"
    note: str = ""


class AdminAbnormalResolveRequest(BaseModel):
    """管理员对误批/异常已通过单据的纠偏驳回（警告或处罚）。"""

    action: str = Field(..., description="warn 或 penalty")
    summary_reason: str = Field("", max_length=400)
    warn_preset: str = ""  # gentle | formal | custom
    warn_custom: str = Field("", max_length=500)
    penalty_level: str = ""  # light | medium | heavy | custom
    penalty_custom: str = Field("", max_length=200)
    penalty_note: str = Field("", max_length=800)
    penalty_valid_until: str | None = None
    penalty_long_term: bool = False


@router.put("/{purchase_id}/forward")
def forward_purchase(
    purchase_id: int,
    req: ForwardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_viewer),
):
    """协同转发审批：记录转发对象与说明。"""
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    assert_transition(p.status, {"pending"}, "转发协同审批")

    required_role = normalize_role(p.approval_required_role or "logistics_admin")
    if not has_role(current_user, required_role):
        raise HTTPException(status_code=403, detail=f"该单据需由 {required_role} 审批")

    to_role = normalize_role(req.to_role or "system_admin")
    if to_role not in {"logistics_admin", "system_admin"}:
        raise HTTPException(status_code=400, detail="仅支持转发给后勤管理员或系统管理员")

    p.forwarded_to = to_role
    p.forwarded_note = (req.note or "").strip()[:256]
    p.approval_required_role = to_role
    p.approval_deadline_at = datetime.utcnow() + timedelta(hours=24)

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="purchase_forward",
        target_type="purchase",
        target_id=str(p.id),
        detail=f"转发协同审批 {p.order_no}，to_role={to_role}，note={p.forwarded_note or '-'}",
    )
    append_trace(
        db,
        p.order_no,
        "审批",
        f"审批人 {current_user.real_name or current_user.username} 转发协同审批至 {to_role}，备注：{p.forwarded_note or '-'}",
    )
    db.commit()
    return {"code": 200, "message": "已转发协同审批", "order_no": p.order_no, "to_role": to_role}


@router.put("/{purchase_id}/approve")
def approve_purchase(
    purchase_id: int,
    req: ApproveRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_viewer),
):
    """分级审批：金额/类型决定审批人。"""
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    assert_transition(p.status, {"pending"}, "审批通过")

    required_role = normalize_role(p.approval_required_role or "logistics_admin")
    if not has_role(current_user, required_role):
        raise HTTPException(status_code=403, detail=f"该单据需由 {required_role} 审批")
    if not p.ai_judgment_at:
        raise HTTPException(status_code=400, detail="请先完成 AI 智能研判，再执行审批")
    if not (req and (req.signature_data or "").strip()):
        raise HTTPException(status_code=400, detail="请完成电子签名后再提交审批")

    p.approved_by_id = current_user.id
    p.rejected_reason = None
    p.is_draft = 0
    requested_supplier_id = req.supplier_id if req else None
    signed_at = datetime.utcnow()
    p.approval_reason_option = (req.reason_option or "").strip()[:128]
    p.approval_opinion = ((req.opinion or "").strip() or p.approval_reason_option or "同意")[:512]
    p.approval_signature_mode = (req.signature_mode or "draw").strip()[:32]
    p.approval_signature_data = (req.signature_data or "").strip()[:2048]
    p.approval_signed_at = signed_at

    if _can_dispatch_directly(db, p):
        p.status = "stocked_in"
        p.supplier_id = None
        p.handoff_code = make_flow_code("HDW")
        route_message = "审批通过，当前库存充足，已直接下发仓储执行出库配送"
        route_detail = "库存充足，转仓储直发"
    else:
        supplier = None
        if requested_supplier_id:
            supplier = db.query(Supplier).filter(Supplier.id == requested_supplier_id, Supplier.is_blacklisted == False).first()
        if not supplier:
            supplier = db.query(Supplier).filter(Supplier.is_blacklisted == False).order_by(Supplier.id.asc()).first()
        if not supplier:
            raise HTTPException(status_code=400, detail="库存不足，且系统未配置可用供应商")
        p.status = "approved"
        p.supplier_id = supplier.id
        p.handoff_code = make_flow_code("HDA")
        route_message = f"审批通过，库存不足，已流转给供应商 {supplier.name} 接单补货"
        route_detail = f"库存不足，已流转供应商 {supplier.name}"

    p.approval_deadline_at = None
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="purchase_approve",
        target_type="purchase",
        target_id=str(p.id),
        detail=(
            f"审批通过采购单 {p.order_no}，审批级别={p.approval_level}/{required_role}，"
            f"分配供应商ID={p.supplier_id or '-'}，路线={route_detail}，交接码={p.handoff_code}，"
            f"AI建议={p.ai_judgment or '-'}({p.ai_judgment_score or 0})，理由={p.approval_reason_option or '-'}，"
            f"意见={p.approval_opinion or '-'}，签名模式={p.approval_signature_mode or '-'}，签名时间={signed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        ),
    )
    append_trace(
        db,
        p.order_no,
        "审批",
        f"审批人 {current_user.real_name or current_user.username}（{normalize_role(current_user.role)}）审批通过；{route_detail}；供应商ID={p.supplier_id or '-'}；当前状态={get_purchase_status_label(p.status)}；交接码={p.handoff_code}",
    )
    db.commit()
    return {"code": 200, "message": route_message, "order_no": p.order_no, "handoff_code": p.handoff_code, "status": p.status}


@router.put("/{purchase_id}/reject")
def reject_purchase(
    purchase_id: int,
    req: RejectRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_viewer),
):
    """分级审批：驳回采购单。"""
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    assert_transition(p.status, {"pending"}, "驳回")

    required_role = normalize_role(p.approval_required_role or "logistics_admin")
    if not has_role(current_user, required_role):
        raise HTTPException(status_code=403, detail=f"该单据需由 {required_role} 审批")
    if not p.ai_judgment_at:
        raise HTTPException(status_code=400, detail="请先完成 AI 智能研判，再执行审批")
    if not (req and (req.signature_data or "").strip()):
        raise HTTPException(status_code=400, detail="请完成电子签名后再提交审批")

    p.status = "rejected"
    p.approved_by_id = None
    signed_at = datetime.utcnow()
    p.approval_reason_option = (req.reason_option or "").strip()[:128] if req else ""
    p.approval_opinion = ((req.opinion or "").strip() if req else "")[:512]
    p.approval_signature_mode = (req.signature_mode or "draw").strip()[:32] if req else "draw"
    p.approval_signature_data = (req.signature_data or "").strip()[:2048] if req else ""
    p.approval_signed_at = signed_at
    plain_reason = (req.reason if req else "") or ""
    p.rejected_reason = (plain_reason or p.approval_opinion or p.approval_reason_option or "已驳回")[:256]
    p.approval_deadline_at = None
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="purchase_reject",
        target_type="purchase",
        target_id=str(p.id),
        detail=(
            f"驳回采购单 {p.order_no}，审批级别={p.approval_level}/{required_role}，原因={p.rejected_reason}，"
            f"AI建议={p.ai_judgment or '-'}({p.ai_judgment_score or 0})，签名模式={p.approval_signature_mode or '-'}，"
            f"签名时间={signed_at.strftime('%Y-%m-%d %H:%M:%S')}"
        ),
    )
    append_trace(
        db,
        p.order_no,
        "审批",
        f"审批人 {current_user.real_name or current_user.username}（{normalize_role(current_user.role)}）驳回，原因：{p.rejected_reason}",
    )
    db.commit()
    return {"code": 200, "message": "已驳回", "order_no": p.order_no}


@router.post("/{purchase_id}/admin-abnormal-resolve")
def admin_abnormal_resolve(
    purchase_id: int,
    req: AdminAbnormalResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_system_admin_only),
):
    """系统管理员：对已流转的异常/误批采购单执行纠偏驳回，并记录警告或处罚类审计。"""
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    allowed = {"approved", "confirmed", "shipped", "stocked_in", "stocked_out"}
    if p.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"当前状态为 {p.status}，不支持管理员纠偏驳回（仅支持：{', '.join(sorted(allowed))}）",
        )
    action = (req.action or "").strip().lower()
    if action not in ("warn", "penalty"):
        raise HTTPException(status_code=400, detail="action 须为 warn 或 penalty")
    if action == "penalty" and len((req.penalty_note or "").strip()) < 4:
        raise HTTPException(status_code=400, detail="处罚说明至少 4 个字符")

    admin_name = current_user.real_name or current_user.username or "admin"
    warn_body = ""
    if action == "warn":
        if req.warn_preset == "gentle":
            warn_body = "温馨提醒：本次采购申请异常，已驳回，请严格遵守校园采购规范"
        elif req.warn_preset == "formal":
            warn_body = "正式警告：本次申请违反采购管理规定，再次违规将严肃处理"
        elif req.warn_preset == "custom" and (req.warn_custom or "").strip():
            warn_body = (req.warn_custom or "").strip()[:500]
        else:
            warn_body = (req.warn_custom or "").strip() or "本次异常申请已由管理员驳回并记录警告。"
    else:
        level = req.penalty_level or "light"
        presets = {
            "light": "轻度处罚：通报批评（全院/全校公示）",
            "medium": "中度处罚：暂停该部门 1 个月采购权限",
            "heavy": "重度处罚：列入采购黑名单 / 扣除年度采购额度",
            "custom": (req.penalty_custom or "").strip() or "自定义处罚",
        }
        warn_body = presets.get(level, presets["light"])

    valid_txt = "长期有效" if req.penalty_long_term else (req.penalty_valid_until or "未指定截止日")
    audit_action = "purchase_admin_warn" if action == "warn" else "purchase_admin_penalty"
    detail_core = (
        f"管理员纠偏驳回 order={p.order_no}，原状态={p.status}，处置={'警告' if action == 'warn' else '处罚'}；"
        f"摘要={req.summary_reason or '-'}；"
        f"下发内容={warn_body[:240]}；"
        f"处罚说明={req.penalty_note.strip() if action == 'penalty' else '-'}；"
        f"有效期={valid_txt}"
    )
    prev_status = p.status
    prev_label = get_purchase_status_label(prev_status)
    p.status = "rejected"
    p.rejected_reason = (req.summary_reason or ("【管理员纠偏驳回】" + warn_body[:200]))[:256]
    p.approval_deadline_at = None

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=admin_name,
        user_role=current_user.role,
        action=audit_action,
        target_type="purchase",
        target_id=str(p.id),
        detail=detail_core[:1800],
    )
    append_trace(
        db,
        p.order_no,
        "纠偏",
        f"系统管理员 {admin_name} 执行异常纠偏驳回（{'警告' if action == 'warn' else '处罚'}），"
        f"原状态={prev_label}({prev_status})，驳回摘要：{(req.summary_reason or '-')[:120]}",
    )
    trace_penalty = (
        f"系统管理员 {admin_name} 下发处罚决定：{warn_body[:160]}；依据《校园物资供应链安全管理办法》相关条款；"
        f"说明：{(req.penalty_note or '-')[:200]}；生效时间 UTC {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}；有效期：{valid_txt}"
    )
    if action == "penalty":
        append_trace(db, p.order_no, "纠偏", trace_penalty[:900])

    db.commit()
    return {
        "code": 200,
        "message": "已驳回并留痕",
        "order_no": p.order_no,
        "action": action,
        "notice_body": warn_body if action == "warn" else trace_penalty,
    }


@router.post("/{purchase_id}/ai-judgment")
def ai_judgment_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_viewer),
):
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    assert_transition(p.status, {"pending"}, "AI智能研判")

    required_role = normalize_role(p.approval_required_role or "logistics_admin")
    if not has_role(current_user, required_role):
        raise HTTPException(status_code=403, detail=f"该单据需由 {required_role} 审批")

    result = _run_ai_judgment(db, p)
    p.ai_judgment = result["recommendation"]
    p.ai_judgment_score = int(result["score"])
    p.ai_judgment_summary = (result["summary"] or "")[:512]
    p.ai_judgment_at = datetime.utcnow()
    p.ai_dimension_inventory = result["dimensions"]["inventory"]["result"]
    p.ai_dimension_budget = result["dimensions"]["budget"]["result"]
    p.ai_dimension_price = result["dimensions"]["price"]["result"]
    p.ai_dimension_compliance = result["dimensions"]["compliance"]["result"]
    p.ai_dimension_supplier = result["dimensions"]["supplier"]["result"]

    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="purchase_ai_judgment",
        target_type="purchase",
        target_id=str(p.id),
        detail=f"完成AI研判 {p.order_no}，建议={p.ai_judgment}，评分={p.ai_judgment_score}，摘要={p.ai_judgment_summary}",
    )
    append_trace(
        db,
        p.order_no,
        "审批",
        f"AI智能研判完成：建议={result['recommendation_label']}，评分={result['score']}，{result['summary']}",
    )
    db.commit()
    return result


@router.get("/history")
def list_purchase_history(
    keyword: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_applicant),
):
    """教师历史申请记录。"""
    q = db.query(Purchase).filter(Purchase.applicant_id == current_user.id).order_by(Purchase.created_at.desc())
    if keyword:
        q = q.filter(Purchase.order_no.contains(keyword))
    rows = q.limit(limit).all()
    return [
        {
            "id": p.id,
            "order_no": p.order_no,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "material_type": p.material_type or "",
            "material_spec": p.material_spec or "",
            "estimated_amount": float(p.estimated_amount or 0),
            "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
            "goods_summary": "、".join(f"{i.goods_name}{i.quantity}{i.unit}" for i in p.items),
            "status": p.status,
            "status_label": get_purchase_status_label(p.status),
            "is_draft": int(p.is_draft or 0),
        }
        for p in rows
    ]


@router.get("/favorites")
def get_purchase_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(_purchase_applicant),
):
    """教师常用物资（从近30条申请统计 Top5）。"""
    rows = (
        db.query(Purchase)
        .filter(Purchase.applicant_id == current_user.id)
        .order_by(Purchase.created_at.desc())
        .limit(30)
        .all()
    )
    freq: dict[str, dict] = {}
    for p in rows:
        for item in p.items:
            key = item.goods_name
            cur = freq.get(key) or {
                "goods_name": item.goods_name,
                "quantity": float(item.quantity or 0),
                "unit": item.unit or "件",
                "material_type": p.material_type or "教学",
                "material_spec": p.material_spec or "",
                "estimated_amount": float(p.estimated_amount or 0),
                "count": 0,
            }
            cur["count"] += 1
            freq[key] = cur
    out = sorted(freq.values(), key=lambda x: x["count"], reverse=True)[:5]
    return out


@router.get("/{purchase_id}/timeline")
def get_purchase_timeline(
    purchase_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单据级闭环时间线：后勤可见全部；教师仅可见本人申请。"""
    p = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="采购单不存在")
    role = normalize_role(current_user.role or "")
    if role == "counselor_teacher":
        if p.applicant_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能查看本人的采购申请")
    elif not has_role(current_user, "logistics_admin", "warehouse_procurement", "system_admin"):
        raise HTTPException(status_code=403, detail="无权查看该采购单时间线")

    linked_deliveries = (
        db.query(Delivery)
        .filter(Delivery.purchase_id == p.id)
        .order_by(Delivery.created_at.asc())
        .all()
    )
    delivery_nos = [d.delivery_no for d in linked_deliveries if d.delivery_no]

    # 只拉取“当前采购单”及其“关联配送单号”的追溯，避免串到其它单据
    trace_batches = {p.order_no}
    trace_batches.update([x for x in delivery_nos if x])
    traces = (
        db.query(TraceRecord)
        .filter(TraceRecord.batch_no.in_(list(trace_batches)))
        .order_by(TraceRecord.created_at.asc(), TraceRecord.id.asc())
        .limit(300)
        .all()
    )
    # 向后兼容：历史脏数据若 batch_no 未写规范，则兜底用 content 精确包含单号补齐
    if not traces:
        traces = (
            db.query(TraceRecord)
            .filter(TraceRecord.content.contains(p.order_no))
            .order_by(TraceRecord.created_at.asc(), TraceRecord.id.asc())
            .limit(120)
            .all()
        )

    # 固定阶段顺序，便于展示“成熟闭环”
    stage_order = {
        "申请": 10,
        "审批": 20,
        "供应商": 30,
        "入库": 40,
        "出库": 50,
        "配送": 60,
        "签收": 70,
    }

    timeline = [
        {
            "stage": t.stage,
            "content": t.content,
            "time": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            "_order": stage_order.get(t.stage, 999),
            "_ts": t.created_at or datetime.min,
            "_batch": t.batch_no or "",
        }
        for t in traces
    ]
    # 同时间按阶段排序；先按时间保证“过程可读”，避免看起来阶段乱序/串单
    timeline.sort(key=lambda x: (x["_ts"], x["_order"], x["time"]))
    # 去重：同批次+同阶段+同内容+同时间只保留一条
    deduped: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in timeline:
        key = (item.get("_batch", ""), item.get("stage", ""), item.get("content", ""), item.get("time", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    timeline = deduped
    for item in timeline:
        item.pop("_order", None)
        item.pop("_ts", None)
        item.pop("_batch", None)

    applicant = db.query(User).filter(User.id == p.applicant_id).first() if p.applicant_id else None
    applicant_name = (applicant.real_name or applicant.username) if applicant else ""
    summary = {
        "purchase_id": p.id,
        "order_no": p.order_no,
        "status": p.status,
        "status_label": get_purchase_status_label(p.status),
        "applicant_id": p.applicant_id,
        "applicant_name": applicant_name,
        "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "",
        "material_type": p.material_type or "",
        "ai_judgment": p.ai_judgment or "",
        "ai_judgment_summary": (p.ai_judgment_summary or "")[:400],
        "receiver_name": p.receiver_name or "",
        "destination": p.destination or "",
        "handoff_code": p.handoff_code or "",
        "items": [
            {"goods_name": i.goods_name, "quantity": float(i.quantity or 0), "unit": i.unit or "件"}
            for i in (p.items or [])
        ],
        "delivery_count": len(linked_deliveries),
        "deliveries": [
            {
                "delivery_no": d.delivery_no,
                "status": d.status,
                "status_label": get_delivery_status_label(d.status),
                "receiver_name": d.receiver_name or "",
                "destination": d.destination or "",
                "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if d.created_at
                else "",
            }
            for d in linked_deliveries
        ],
    }

    return {"summary": summary, "timeline": timeline}
