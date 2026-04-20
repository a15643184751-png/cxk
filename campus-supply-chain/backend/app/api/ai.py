"""AI 智能体接口：接入业务数据，生成决策与可执行动作"""
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..models.purchase import Purchase, PurchaseItem
from ..models.chat_history import ChatHistory
from ..api.deps import get_current_user, normalize_role
from ..services.agent import process_chat
from ..services.flow import make_flow_code, append_trace

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    """use_agent=True：教师走工具与申领清单；False：优先纯对话（小链直接回复）。"""

    message: str
    session_id: str | None = None
    use_agent: bool = False


class ExecuteRequest(BaseModel):
    type: str
    payload: dict | None = None


@router.post("/chat")
def ai_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_id = req.session_id or str(uuid.uuid4())
    # 加载历史对话
    history_rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at.asc())
        .limit(16)
        .all()
    )
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    role = normalize_role(current_user.role or "")
    display = (current_user.real_name or current_user.username or "").strip()
    data = process_chat(
        db,
        req.message,
        applicant_id=current_user.id,
        history=history,
        user_role=role,
        caller_display_name=display or None,
        use_agent=req.use_agent,
    )
    db.add(ChatHistory(session_id=session_id, user_id=current_user.id, agent_type="purchase", role="user", content=req.message))
    db.add(ChatHistory(session_id=session_id, user_id=current_user.id, agent_type="purchase", role="assistant", content=data.get("reply", "")))
    db.commit()
    return {"code": 200, "data": {**data, "session_id": session_id}}


@router.post("/execute")
def ai_execute(
    req: ExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if req.type == "create_purchase":
        payload = req.payload or {}
        items = payload.get("items", [])
        receiver_name = (payload.get("receiver_name") or "").strip() or (current_user.real_name or current_user.username or "")
        destination = (payload.get("destination") or "").strip()
        order_no = f"PO{datetime.now().strftime('%Y%m%d%H%M%S')}"
        handoff_code = make_flow_code("HDP")
        purchase = Purchase(
            order_no=order_no,
            status="pending",
            applicant_id=current_user.id,
            receiver_name=receiver_name,
            destination=destination,
            handoff_code=handoff_code,
        )
        db.add(purchase)
        db.flush()
        for it in items:
            db.add(
                PurchaseItem(
                    purchase_id=purchase.id,
                    goods_name=it.get("name", ""),
                    quantity=float(it.get("quantity", 0)),
                    unit=it.get("unit", ""),
                )
            )
        items_desc = "；".join(f"{it.get('name','')}{it.get('quantity',0)}{it.get('unit','')}" for it in items)
        append_trace(
            db,
            order_no,
            "申请",
            f"申请人 {current_user.real_name or current_user.username} 提交采购申请：{items_desc}；收货人={receiver_name or '-'}；目的地={destination or '-'}；交接码={handoff_code}",
        )
        db.commit()
        is_teacher = normalize_role(current_user.role) == "counselor_teacher"
        return {
            "code": 200,
            "data": {
                "success": True,
                "orderNo": order_no,
                "message": "申请已提交，等待管理员审批" if is_teacher else "采购单已创建",
                "trace": {
                    "action": "create_purchase",
                    "executedAt": datetime.now().isoformat(),
                    "items": items,
                },
            },
        }
    return {"code": 200, "data": {"success": True}}
