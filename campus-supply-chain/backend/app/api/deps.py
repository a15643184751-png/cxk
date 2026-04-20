from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..core.security import decode_token

security = HTTPBearer(auto_error=False)

ROLE_ALIASES = {
    # 新角色
    "system_admin": "system_admin",                # 平台管理员
    "logistics_admin": "logistics_admin",            # 后勤管理员
    "warehouse_procurement": "warehouse_procurement",  # 仓储采购员
    "campus_supplier": "campus_supplier",            # 校园合作供应商
    "counselor_teacher": "counselor_teacher",        # 辅导员教师
    # 兼容旧角色
    "admin": "system_admin",
    "procurement": "warehouse_procurement",
    "supplier": "campus_supplier",
    "teacher": "counselor_teacher",
}


def normalize_role(role: str | None) -> str:
    return ROLE_ALIASES.get((role or "").strip(), (role or "").strip())


def has_role(user: User, *allowed: str) -> bool:
    user_role = normalize_role(user.role)
    allowed_norm = {normalize_role(x) for x in allowed}
    return user_role in allowed_norm


def require_roles(*allowed: str):
    """依赖：仅允许指定角色访问"""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_role(current_user, *allowed):
            raise HTTPException(status_code=403, detail="无权限访问")
        return current_user
    return _check


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token 无效")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
