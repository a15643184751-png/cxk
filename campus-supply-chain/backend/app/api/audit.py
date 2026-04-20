from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.audit_log import AuditLog
from ..models.user import User
from ..api.deps import require_roles

router = APIRouter(prefix="/audit", tags=["audit"])
_allowed = require_roles("system_admin")  # 仅管理员可查看审计


@router.get("")
def list_audit_logs(
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_allowed),
):
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    items = q.limit(400).all()
    return [
        {
            "id": x.id,
            "user_name": x.user_name,
            "user_role": x.user_role,
            "action": x.action,
            "target_type": x.target_type,
            "target_id": x.target_id,
            "detail": x.detail,
            "created_at": x.created_at.isoformat() if x.created_at else None,
        }
        for x in items
    ]
