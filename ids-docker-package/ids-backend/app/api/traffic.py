from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .deps import require_roles
from ..database import get_db
from ..models.ids_http_session import IDSHTTPSession
from ..models.user import User
from ..services.ids_blocklist import (
    add_blocked_ip,
    get_blocked_ip,
    is_ip_blocked,
    list_blocked_ips,
    remove_blocked_ip,
)

router = APIRouter(prefix="/traffic", tags=["traffic"])
_ids_user = require_roles("ids_admin", "ids_operator", "ids_auditor", "ids_viewer")
_ids_operator = require_roles("ids_admin", "ids_operator")


class BlocklistMutationRequest(BaseModel):
    ip: str
    note: str | None = None


def _serialize_session(item: IDSHTTPSession) -> dict:
    return {
        "id": int(item.id),
        "client_ip": item.client_ip,
        "scheme": item.scheme,
        "host": item.host,
        "method": item.method,
        "path": item.path,
        "query_string": item.query_string,
        "route_kind": item.route_kind,
        "upstream_base": item.upstream_base,
        "upstream_url": item.upstream_url,
        "user_agent": item.user_agent,
        "request_headers": item.request_headers,
        "request_body": item.request_body,
        "raw_request": item.raw_request,
        "request_size": item.request_size,
        "response_status": item.response_status,
        "response_headers": item.response_headers,
        "response_body": item.response_body,
        "raw_response": item.raw_response,
        "response_size": item.response_size,
        "content_type": item.content_type,
        "duration_ms": item.duration_ms,
        "blocked": item.blocked,
        "attack_type": item.attack_type,
        "risk_score": item.risk_score,
        "confidence": item.confidence,
        "incident_id": item.incident_id,
        "response_note": item.response_note,
        "ip_policy_blocked": is_ip_blocked(item.client_ip),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _serialize_blocked_ip(db: Session, item: dict) -> dict:
    ip = str(item.get("ip") or "").strip()
    query = db.query(IDSHTTPSession).filter(IDSHTTPSession.client_ip == ip)
    last_session = query.order_by(desc(IDSHTTPSession.created_at), desc(IDSHTTPSession.id)).first()
    return {
        "ip": ip,
        "source": str(item.get("source") or "manual_block"),
        "actor": str(item.get("actor") or "system"),
        "note": str(item.get("note") or ""),
        "event_id": item.get("event_id"),
        "blocked_at": item.get("blocked_at"),
        "updated_at": item.get("updated_at"),
        "total_sessions": query.count(),
        "blocked_sessions": query.filter(IDSHTTPSession.blocked == 1).count(),
        "last_seen_at": last_session.created_at.isoformat() if last_session and last_session.created_at else None,
        "last_path": last_session.path if last_session else "",
        "last_status": int(last_session.response_status or 0) if last_session else 0,
    }


@router.get("/sessions")
def list_http_sessions(
    method: str | None = None,
    client_ip: str | None = None,
    route_kind: str | None = None,
    blocked: int | None = None,
    path_keyword: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(_ids_user),
):
    query = db.query(IDSHTTPSession)
    if method:
        query = query.filter(IDSHTTPSession.method == method.upper())
    if client_ip:
        query = query.filter(IDSHTTPSession.client_ip.contains(client_ip.strip()))
    if route_kind:
        query = query.filter(IDSHTTPSession.route_kind == route_kind.strip())
    if blocked in (0, 1):
        query = query.filter(IDSHTTPSession.blocked == blocked)
    if path_keyword:
        query = query.filter(IDSHTTPSession.path.contains(path_keyword.strip()))

    total = query.count()
    items = (
        query.order_by(desc(IDSHTTPSession.created_at), desc(IDSHTTPSession.id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    summary = {
        "total": total,
        "blocked_count": db.query(IDSHTTPSession).filter(IDSHTTPSession.blocked == 1).count(),
        "api_count": db.query(IDSHTTPSession).filter(IDSHTTPSession.route_kind == "api").count(),
        "frontend_count": db.query(IDSHTTPSession).filter(IDSHTTPSession.route_kind == "frontend").count(),
        "active_blocked_ips": len(list_blocked_ips()),
    }
    return {"total": total, "items": [_serialize_session(item) for item in items], "summary": summary}


@router.get("/sessions/{session_id}")
def get_http_session(
    session_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_ids_user),
):
    item = db.query(IDSHTTPSession).filter(IDSHTTPSession.id == session_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="session not found")
    payload = _serialize_session(item)
    payload["request_headers_json"] = item.request_headers or ""
    payload["response_headers_json"] = item.response_headers or ""
    return payload


@router.get("/sessions/recent/raw")
def get_recent_raw_preview(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(_ids_user),
):
    items = (
        db.query(IDSHTTPSession)
        .order_by(desc(IDSHTTPSession.created_at), desc(IDSHTTPSession.id))
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": int(item.id),
                "request_line": f"{item.method} {item.path}{'?' + item.query_string if item.query_string else ''}",
                "response_status": item.response_status,
                "blocked": item.blocked,
                "attack_type": item.attack_type,
                "ip_policy_blocked": is_ip_blocked(item.client_ip),
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in items
        ]
    }


@router.get("/blocklist")
def get_blocklist(
    db: Session = Depends(get_db),
    _: User = Depends(_ids_user),
):
    items = list_blocked_ips()
    serialized = [_serialize_blocked_ip(db, item) for item in items]
    return {
        "total": len(serialized),
        "items": serialized,
    }


@router.post("/blocklist")
def add_to_blocklist(
    req: BlocklistMutationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_ids_operator),
):
    actor = current_user.username or getattr(current_user, "real_name", "") or "ids_operator"
    ok, message = add_blocked_ip(
        req.ip,
        source="traffic_policy",
        actor=actor,
        note=(req.note or "").strip() or None,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    item = get_blocked_ip(req.ip)
    if item is None:
        items = list_blocked_ips()
        item = items[0] if items else {"ip": req.ip.strip()}
    return {
        "ok": True,
        "message": message,
        "item": _serialize_blocked_ip(db, item),
    }


@router.post("/blocklist/remove")
def remove_from_blocklist(
    req: BlocklistMutationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_ids_operator),
):
    ok, message = remove_blocked_ip(req.ip)
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    return {
        "ok": True,
        "message": message,
        "total": len(list_blocked_ips()),
    }
