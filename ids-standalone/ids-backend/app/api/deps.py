import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..config import settings
from ..core.security import decode_token
from ..database import get_db
from ..models.user import User

security = HTTPBearer(auto_error=False)

ROLE_ALIASES = {
    "ids_admin": "ids_admin",
    "ids_operator": "ids_operator",
    "ids_auditor": "ids_auditor",
    "ids_viewer": "ids_viewer",
    "system_admin": "ids_admin",
    "admin": "ids_admin",
}


@dataclass(frozen=True)
class IntegrationPrincipal:
    source_system: str
    subject: str
    role: str = "integration"


def normalize_role(role: str | None) -> str:
    return ROLE_ALIASES.get((role or "").strip(), (role or "").strip())


def has_role(user: User, *allowed: str) -> bool:
    user_role = normalize_role(user.role)
    allowed_norm = {normalize_role(item) for item in allowed}
    return user_role in allowed_norm


def _decode_user_from_creds(
    creds: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User | None:
    if not creds or not creds.credentials:
        return None

    payload = decode_token(creds.credentials)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        return db.query(User).filter(User.id == int(user_id)).first()
    except (TypeError, ValueError):
        return None


def _integration_token_matches(candidate: str | None) -> bool:
    expected = (settings.IDS_INTEGRATION_TOKEN or "").strip()
    provided = (candidate or "").strip()
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided, expected)


def _integration_source_name(request: Request) -> str:
    raw = (
        request.headers.get("x-ids-source-system")
        or request.headers.get("x-source-system")
        or "site-integration"
    )
    cleaned = " ".join(raw.strip().split())
    return (cleaned or "site-integration")[:64]


def _is_loopback_request(request: Request) -> bool:
    host = (
        (request.client.host if request.client else "")
        or request.headers.get("x-real-ip")
        or request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    )
    return host in {"127.0.0.1", "::1", "localhost"}


def _integration_from_request(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
) -> IntegrationPrincipal | None:
    header_token = request.headers.get("x-ids-integration-token")
    if _integration_token_matches(header_token):
        source_system = _integration_source_name(request)
        return IntegrationPrincipal(
            source_system=source_system,
            subject=f"integration::{source_system}",
        )

    bearer_token = creds.credentials if creds else ""
    if _integration_token_matches(bearer_token):
        source_system = _integration_source_name(request)
        return IntegrationPrincipal(
            source_system=source_system,
            subject=f"integration::{source_system}",
        )

    expected = (settings.IDS_INTEGRATION_TOKEN or "").strip()
    if not expected and _is_loopback_request(request):
        source_system = _integration_source_name(request)
        if source_system and source_system != "site-integration":
            return IntegrationPrincipal(
                source_system=source_system,
                subject=f"loopback::{source_system}",
            )

    return None


def require_roles(*allowed: str):
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_role(current_user, *allowed):
            raise HTTPException(status_code=403, detail="Forbidden IDS resource")
        return current_user

    return _check


def require_roles_or_integration(*allowed: str):
    def _check(
        request: Request,
        creds: HTTPAuthorizationCredentials | None = Depends(security),
        db: Session = Depends(get_db),
    ) -> User | IntegrationPrincipal:
        user = _decode_user_from_creds(creds, db)
        if user is not None:
            if not has_role(user, *allowed):
                raise HTTPException(status_code=403, detail="Forbidden IDS resource")
            return user

        integration = _integration_from_request(request, creds)
        if integration is not None:
            return integration

        raise HTTPException(status_code=401, detail="Authentication required")

    return _check


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    user = _decode_user_from_creds(creds, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
