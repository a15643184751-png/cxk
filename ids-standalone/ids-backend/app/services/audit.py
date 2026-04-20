from sqlalchemy.orm import Session
from ..models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    *,
    user_id: int | None,
    user_name: str,
    user_role: str,
    action: str,
    target_type: str,
    target_id: str,
    detail: str,
):
    db.add(
        AuditLog(
            user_id=user_id,
            user_name=user_name or "",
            user_role=user_role or "",
            action=action,
            target_type=target_type,
            target_id=str(target_id or ""),
            detail=detail[:512] if detail else "",
        )
    )
