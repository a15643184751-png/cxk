from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.warning import Warning
from ..models.user import User
from ..api.deps import require_roles
from ..services.audit import write_audit_log

router = APIRouter(prefix="/warning", tags=["warning"])
_warning_viewer = require_roles("logistics_admin", "warehouse_procurement")
_warning_handler = require_roles("logistics_admin", "warehouse_procurement")


class HandleWarningRequest(BaseModel):
    action_note: str = ""


@router.get("")
def list_warnings(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_warning_viewer),
):
    q = db.query(Warning).order_by(Warning.created_at.desc())
    if status:
        q = q.filter(Warning.status == status)
    return [
        {
            "id": w.id,
            "level": w.level,
            "material": w.material,
            "description": w.description,
            "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        }
        for w in q.all()
    ]


@router.put("/{warning_id}/handle")
def handle_warning(
    warning_id: int,
    req: HandleWarningRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_warning_handler),
):
    """标记预警为已处理"""
    w = db.query(Warning).filter(Warning.id == warning_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="预警不存在")
    w.status = "handled"
    note = (req.action_note if req else "") or "已处理"
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=current_user.real_name or current_user.username,
        user_role=current_user.role,
        action="warning_handle",
        target_type="warning",
        target_id=str(w.id),
        detail=f"处理预警（{w.material}）：{note}",
    )
    db.commit()
    return {"code": 200, "message": "已处理", "action_note": note}
