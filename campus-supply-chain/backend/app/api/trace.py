from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.trace import TraceRecord
from ..models.purchase import Purchase
from ..models.delivery import Delivery
from ..models.user import User
from ..api.deps import get_current_user, has_role
from ..services.flow import get_delivery_status_label, get_purchase_status_label

router = APIRouter(prefix="/trace", tags=["trace"])


@router.get("/query")
def trace_query(
    keyword: str | None = Query(None, min_length=1),
    query_type: str = Query("all"),  # all | batch | order | stock
    batch_no: str | None = Query(None, min_length=1),  # backward compatibility
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if has_role(current_user, "campus_supplier"):
        raise HTTPException(status_code=403, detail="供应商无权访问全局溯源")

    key = (keyword or batch_no or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="请输入查询关键字")

    purchase = (
        db.query(Purchase)
        .filter(
            or_(
                Purchase.order_no == key,
                Purchase.handoff_code == key,
            )
        )
        .first()
    )
    delivery = (
        db.query(Delivery)
        .filter(
            or_(
                Delivery.delivery_no == key,
                Delivery.handoff_code == key,
            )
        )
        .first()
    )
    if not purchase and delivery and delivery.purchase_id:
        purchase = db.query(Purchase).filter(Purchase.id == delivery.purchase_id).first()

    # 教师仅可查询本人申请闭环相关链路
    if has_role(current_user, "counselor_teacher"):
        if not purchase or purchase.applicant_id != current_user.id:
            raise HTTPException(status_code=403, detail="仅可查询本人申请相关链路")

    trace_keys = {key}
    content_keywords = {key}
    if purchase:
        trace_keys.add(purchase.order_no)
        content_keywords.update({
            purchase.order_no,
            purchase.handoff_code or "",
            purchase.destination or "",
            purchase.receiver_name or "",
        })
        linked_deliveries = db.query(Delivery).filter(Delivery.purchase_id == purchase.id).all()
        for item in linked_deliveries:
            trace_keys.add(item.delivery_no)
            content_keywords.update({item.delivery_no, item.handoff_code or "", item.destination or "", item.receiver_name or ""})
    elif delivery:
        trace_keys.add(delivery.delivery_no)
        content_keywords.update({delivery.delivery_no, delivery.handoff_code or "", delivery.destination or "", delivery.receiver_name or ""})

    q = db.query(TraceRecord)
    filters = [TraceRecord.batch_no.in_([x for x in trace_keys if x])]
    for term in [x for x in content_keywords if x]:
        filters.append(TraceRecord.content.contains(term))
    q = q.filter(or_(*filters))

    records = q.order_by(TraceRecord.created_at).limit(200).all()
    summary = None
    if purchase:
        latest_delivery = (
            db.query(Delivery)
            .filter(Delivery.purchase_id == purchase.id)
            .order_by(Delivery.created_at.desc())
            .first()
        )
        applicant = db.query(User).filter(User.id == purchase.applicant_id).first() if purchase.applicant_id else None
        summary = {
            "order_no": purchase.order_no,
            "status": purchase.status,
            "status_label": get_purchase_status_label(purchase.status),
            "handoff_code": purchase.handoff_code or "",
            "receiver_name": purchase.receiver_name or "",
            "destination": purchase.destination or "",
            "applicant_name": (applicant.real_name or applicant.username) if applicant else "-",
            "delivery_no": latest_delivery.delivery_no if latest_delivery else "",
            "delivery_status": latest_delivery.status if latest_delivery else "",
            "delivery_status_label": get_delivery_status_label(latest_delivery.status) if latest_delivery else "",
            "trace_count": len(records),
        }

    return {
        "summary": summary,
        "records": [
            {
                "trace_key": r.batch_no,
                "stage": r.stage,
                "content": r.content,
                "time": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
            }
            for r in records
        ],
    }
