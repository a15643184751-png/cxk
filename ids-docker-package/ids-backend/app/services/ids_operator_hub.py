from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape
import json
from pathlib import Path
import re
import smtplib
import ssl
import threading
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal
from ..models.audit_log import AuditLog
from ..models.ids_event import IDSEvent
from .audit import write_audit_log

_STATE_DIR = Path(settings.IDS_OPERATOR_STATE_DIR)
_NOTIFICATION_SETTINGS_PATH = _STATE_DIR / "notification_settings.json"
_FALSE_POSITIVE_MEMORY_PATH = _STATE_DIR / "false_positive_memory.json"
_AUTO_NOTIFICATION_STATE_PATH = _STATE_DIR / "auto_notification_state.json"
_AUTO_NOTIFICATION_MIN_SCORE = 80
_AUTO_NOTIFICATION_DEMO_WINDOW_SECONDS = 90
_DEMO_BURST_DETECTORS = {
    "asset_guard",
    "auth_guard",
    "ids_policy",
    "ip_blocklist",
    "login_guard",
    "mail_dispatch",
    "request_guard",
    "review_queue",
    "route_guard",
    "traffic_policy",
    "upload_audit",
    "upload_guard",
    "waf_bridge",
    "workflow_guard",
}
_DEMO_RECON_PATHS = {
    "/docs/index",
    "/api/openapi/catalog",
    "/api/auth/login/probe",
    "/admin/console/ping",
    "/actuator/health/check",
    "/admin/export/template/check",
}

_ATTACK_TYPE_LABELS = {
    "sql_injection": "SQL Injection",
    "xss": "XSS",
    "xxe": "XXE",
    "xml_external_entity": "XXE",
    "path_traversal": "Path Traversal",
    "cmd_injection": "Command Injection",
    "command_injection": "Command Injection",
    "scanner": "Scanner",
    "malformed": "Malformed Request",
    "jndi_injection": "JNDI Injection",
    "prototype_pollution": "Prototype Pollution",
    "malware": "Malware Upload",
    "recon_finding": "Scanner",
    "recon_port_exposure": "Scanner",
    "recon_nday_candidate": "Scanner",
    "recon_security_header_gap": "Scanner",
    "recon_js_secret_hint": "Scanner",
    "recon_login_surface": "Scanner",
    "recon_sensitive_function": "Scanner",
    "demo_attack_detected": "Scanner",
    "demo_defense_effective": "Protective Action",
    "suspicious_attack_activity": "Scanner",
    "protective_containment_action": "Protective Action",
}

_ATTACK_TYPE_LABELS_ZH = {
    "sql_injection": "SQL 注入",
    "xss": "跨站脚本",
    "xxe": "XXE",
    "xml_external_entity": "XXE",
    "path_traversal": "路径穿越",
    "cmd_injection": "命令注入",
    "command_injection": "命令注入",
    "scanner": "扫描探测",
    "malformed": "异常请求",
    "jndi_injection": "JNDI 注入",
    "prototype_pollution": "原型污染",
    "malware": "恶意文件上传",
    "recon_finding": "扫描探测",
    "recon_port_exposure": "扫描探测",
    "recon_nday_candidate": "扫描探测",
    "recon_security_header_gap": "扫描探测",
    "recon_js_secret_hint": "扫描探测",
    "recon_login_surface": "扫描探测",
    "recon_sensitive_function": "扫描探测",
    "demo_attack_detected": "扫描探测",
    "demo_defense_effective": "安全处置",
    "suspicious_attack_activity": "扫描探测",
    "protective_containment_action": "安全处置",
}

_EMAIL_BRAND_NAME = "校园供应链 IDS 告警中心"


def _ensure_state_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json_file(path: Path, payload: Any) -> None:
    _ensure_state_dir()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_auto_notification_state() -> dict[str, Any]:
    raw = _read_json_file(_AUTO_NOTIFICATION_STATE_PATH, {})
    return raw if isinstance(raw, dict) else {}


def _save_auto_notification_state(payload: dict[str, Any]) -> None:
    _write_json_file(_AUTO_NOTIFICATION_STATE_PATH, payload)


def _auto_notification_throttle_key(event_like: dict[str, Any]) -> str:
    client_ip = str(event_like.get("client_ip") or "").strip() or "unknown"
    detector_name = str(event_like.get("detector_name") or "").strip().lower()
    path = _normalize_path(event_like.get("path"))
    if (
        detector_name not in _DEMO_BURST_DETECTORS
        and path not in _DEMO_RECON_PATHS
        and not path.startswith("/defense/")
        and not path.endswith("-check")
    ):
        return ""
    if path.startswith("/defense/"):
        phase = "containment"
    elif path in _DEMO_RECON_PATHS or detector_name in {"asset_guard", "login_guard", "route_guard", "traffic_policy"}:
        phase = "recon"
    else:
        phase = "probe"
    return f"demo-burst::{client_ip}::{phase}"


def _claim_auto_notification_slot(event_like: dict[str, Any]) -> tuple[bool, str]:
    throttle_key = _auto_notification_throttle_key(event_like)
    if not throttle_key:
        return True, ""

    now = datetime.utcnow()
    window = timedelta(seconds=_AUTO_NOTIFICATION_DEMO_WINDOW_SECONDS)
    cutoff = now - timedelta(minutes=30)
    state = _load_auto_notification_state()
    trimmed: dict[str, Any] = {}
    for key, item in state.items():
        if not isinstance(item, dict):
            continue
        raw_sent_at = str(item.get("last_sent_at") or "").strip()
        try:
            sent_at = datetime.fromisoformat(raw_sent_at)
        except Exception:
            continue
        if sent_at >= cutoff:
            trimmed[key] = {"last_sent_at": sent_at.isoformat()}

    current = trimmed.get(throttle_key) or {}
    raw_last_sent = str(current.get("last_sent_at") or "").strip()
    if raw_last_sent:
        try:
            last_sent_at = datetime.fromisoformat(raw_last_sent)
        except Exception:
            last_sent_at = None
        else:
            if now - last_sent_at < window:
                return False, f"throttled within {_AUTO_NOTIFICATION_DEMO_WINDOW_SECONDS}s window"

    trimmed[throttle_key] = {"last_sent_at": now.isoformat()}
    _save_auto_notification_state(trimmed)
    return True, ""


def _attack_type_label(attack_type: str | None) -> str:
    key = str(attack_type or "").strip().lower()
    return _ATTACK_TYPE_LABELS.get(key, key.replace("_", " ").title() or "Unknown")


def _attack_type_label_zh(attack_type: str | None, *, fallback: str = "") -> str:
    key = str(attack_type or "").strip().lower()
    if key in _ATTACK_TYPE_LABELS_ZH:
        return _ATTACK_TYPE_LABELS_ZH[key]
    return fallback or _attack_type_label(attack_type)


def _normalize_path(path: str | None) -> str:
    raw = str(path or "").strip().split("?", 1)[0] or "/"
    raw = raw.rstrip("/") or "/"
    raw = re.sub(r"/\d+", "/:id", raw)
    raw = re.sub(r"/[0-9a-fA-F]{8,}", "/:token", raw)
    return raw


def _path_prefix(path: str | None) -> str:
    normalized = _normalize_path(path)
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return "/"
    return "/" + "/".join(parts[:2])


def _format_dt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _derive_location_from_ip(client_ip: str | None) -> dict[str, object]:
    points = [
        {"country": "China", "city": "Changchun", "lat": 43.817, "lng": 125.3235},
        {"country": "United States", "city": "New York", "lat": 40.7128, "lng": -74.0060},
        {"country": "United States", "city": "Los Angeles", "lat": 34.0522, "lng": -118.2437},
        {"country": "Japan", "city": "Tokyo", "lat": 35.6762, "lng": 139.6503},
        {"country": "Germany", "city": "Berlin", "lat": 52.52, "lng": 13.4050},
        {"country": "Singapore", "city": "Singapore", "lat": 1.3521, "lng": 103.8198},
    ]
    digest = sum(ord(char) for char in str(client_ip or "0.0.0.0"))
    point = points[digest % len(points)]
    return {**point, "derived": True}


def _ua_family(user_agent: str | None) -> str:
    ua = str(user_agent or "").lower()
    if "chrome" in ua and "edg/" not in ua:
        return "Chrome"
    if "edg/" in ua:
        return "Edge"
    if "firefox" in ua:
        return "Firefox"
    if "safari" in ua and "chrome" not in ua:
        return "Safari"
    if "postman" in ua:
        return "Postman"
    if "python" in ua or "requests" in ua:
        return "Python Client"
    if "curl" in ua:
        return "curl"
    return "Unknown"


def _serialize_mini_event(row: IDSEvent) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "created_at": _format_dt(row.created_at),
        "attack_type": row.attack_type or "",
        "attack_type_label": _attack_type_label(row.attack_type),
        "risk_score": int(row.risk_score or 0),
        "status": row.status or "new",
        "blocked": bool(row.blocked),
        "method": row.method or "",
        "path": row.path or "",
        "signature_matched": row.signature_matched or "",
        "detector_name": row.detector_name or "",
        "response_detail": (row.response_detail or "")[:255],
    }


def _default_notification_settings() -> dict[str, Any]:
    return {
        "email": {
            "enabled": False,
            "smtp_host": "",
            "smtp_port": 465,
            "username": "",
            "password": "",
            "from_addr": "",
            "to_addrs": "",
            "use_tls": False,
            "use_ssl": True,
        },
        "wecom": {
            "enabled": False,
            "webhook_url": "",
        },
        "webhook": {
            "enabled": False,
            "url": "",
            "secret": "",
        },
    }


def load_notification_settings() -> dict[str, Any]:
    settings = _read_json_file(_NOTIFICATION_SETTINGS_PATH, _default_notification_settings())
    merged = _default_notification_settings()
    for channel in ("email", "wecom", "webhook"):
        merged[channel].update(settings.get(channel, {}))
    return merged


def public_notification_settings() -> dict[str, Any]:
    settings = load_notification_settings()
    email = dict(settings["email"])
    webhook = dict(settings["webhook"])
    email["password_configured"] = bool(email.get("password"))
    email["password"] = ""
    webhook["secret_configured"] = bool(webhook.get("secret"))
    webhook["secret"] = ""
    return {
        "email": email,
        "wecom": dict(settings["wecom"]),
        "webhook": webhook,
    }


def save_notification_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_notification_settings()
    merged = _default_notification_settings()
    for channel in ("email", "wecom", "webhook"):
        merged[channel].update(current.get(channel, {}))
        incoming = payload.get(channel, {}) if isinstance(payload, dict) else {}
        merged[channel].update(incoming)
    if not str(merged["email"].get("password") or "").strip():
        merged["email"]["password"] = str(current["email"].get("password") or "")
    if not str(merged["webhook"].get("secret") or "").strip():
        merged["webhook"]["secret"] = str(current["webhook"].get("secret") or "")
    merged["email"]["smtp_port"] = int(merged["email"].get("smtp_port") or 465)
    merged["email"]["use_ssl"] = bool(merged["email"].get("use_ssl"))
    merged["email"]["use_tls"] = bool(merged["email"].get("use_tls"))
    if merged["email"]["use_ssl"] and merged["email"]["use_tls"]:
        merged["email"]["use_tls"] = False
    _write_json_file(_NOTIFICATION_SETTINGS_PATH, merged)
    return public_notification_settings()


def _build_notification_payload(event_like: dict[str, Any], *, is_test: bool = False) -> dict[str, Any]:
    event_id = int(event_like.get("id") or event_like.get("event_id") or 0)
    attack_type = str(event_like.get("attack_type") or "")
    attack_type_label = str(
        event_like.get("attack_type_label")
        or _attack_type_label(attack_type)
    )
    attack_type_label_zh = _attack_type_label_zh(attack_type, fallback=attack_type_label)
    risk_score = int(event_like.get("risk_score") or 0)
    path = str(event_like.get("path") or "/")
    client_ip = str(event_like.get("client_ip") or "-")
    method = str(event_like.get("method") or "")
    status = str(event_like.get("status") or "new")
    blocked = bool(event_like.get("blocked"))
    detector_name = str(event_like.get("detector_name") or "-")
    summary = str(
        event_like.get("response_detail")
        or event_like.get("signature_matched")
        or event_like.get("summary")
        or ""
    ).strip()
    title = (
        f"【校园供应链 IDS 测试】攻击告警联动测试 #{event_id or 'demo'} · {attack_type_label_zh}"
        if is_test
        else f"【校园供应链 IDS 告警】高风险{attack_type_label_zh}事件 #{event_id}"
    )
    body = (
        f"风险分 {risk_score} / 来源 IP {client_ip} / 路径 {path} / 检测器 {detector_name}"
    )
    return {
        "title": title,
        "body": body,
        "event": {
            "id": event_id,
            "attack_type": attack_type,
            "attack_type_label": attack_type_label,
            "attack_type_label_zh": attack_type_label_zh,
            "client_ip": client_ip,
            "path": path,
            "method": method,
            "risk_score": risk_score,
            "status": status,
            "blocked": blocked,
            "created_at": str(event_like.get("created_at") or ""),
            "detector_name": detector_name,
            "summary": summary,
        },
    }


def _format_email_sender(settings: dict[str, Any]) -> str:
    base_addr = str(settings.get("from_addr") or settings.get("username") or "ids@localhost").strip()
    if not base_addr:
        return f"{_EMAIL_BRAND_NAME} <ids@localhost>"
    if "<" in base_addr and ">" in base_addr:
        return base_addr
    return f"{_EMAIL_BRAND_NAME} <{base_addr}>"


def _plain_email_content(payload: dict[str, Any]) -> str:
    event = payload["event"]
    blocked_label = "是" if event["blocked"] else "否"
    summary = event.get("summary") or "暂无额外摘要。"
    return (
        "校园供应链 IDS 攻击告警通知\n"
        "====================\n\n"
        f"告警标题：{payload['title']}\n"
        f"攻击类型：{event.get('attack_type_label_zh') or event.get('attack_type_label')}\n"
        f"风险分：{event['risk_score']}\n"
        f"来源 IP：{event['client_ip']}\n"
        f"请求方法：{event['method'] or '-'}\n"
        f"请求路径：{event['path']}\n"
        f"当前状态：{event['status']}\n"
        f"是否阻断：{blocked_label}\n"
        f"检测器：{event['detector_name']}\n"
        f"事件时间：{event['created_at'] or '-'}\n"
        f"事件编号：{event['id'] or '-'}\n\n"
        f"摘要：{summary}\n\n"
        "说明：该邮件由校园供应链 IDS 自动发送，请尽快登录本地 IDS 控制台复核。\n"
    )


def _html_email_content(payload: dict[str, Any]) -> str:
    event = payload["event"]
    blocked_label = "已阻断" if event["blocked"] else "待复核"
    blocked_bg = "#dc2626" if event["blocked"] else "#f59e0b"
    attack_label = event.get("attack_type_label_zh") or event.get("attack_type_label") or "-"
    summary = event.get("summary") or "暂无额外摘要。"
    rows = [
        ("攻击类型", attack_label),
        ("风险分", str(event.get("risk_score") or 0)),
        ("来源 IP", event.get("client_ip") or "-"),
        ("请求方法", event.get("method") or "-"),
        ("请求路径", event.get("path") or "-"),
        ("当前状态", event.get("status") or "-"),
        ("检测器", event.get("detector_name") or "-"),
        ("事件时间", event.get("created_at") or "-"),
        ("事件编号", str(event.get("id") or "-")),
    ]
    detail_rows = "".join(
        f"<tr><td style='padding:10px 12px;color:#475569;border-bottom:1px solid #e2e8f0;width:120px;'>{escape(label)}</td>"
        f"<td style='padding:10px 12px;color:#0f172a;border-bottom:1px solid #e2e8f0;'>{escape(value)}</td></tr>"
        for label, value in rows
    )
    return (
        "<html><body style='margin:0;padding:24px;background:#f1f5f9;font-family:Segoe UI,Microsoft YaHei,Arial,sans-serif;'>"
        "<div style='max-width:760px;margin:0 auto;background:#ffffff;border-radius:18px;"
        "box-shadow:0 18px 45px rgba(15,23,42,0.12);overflow:hidden;border:1px solid #dbeafe;'>"
        "<div style='padding:22px 24px;background:linear-gradient(135deg,#220a0a,#7f1d1d 58%,#991b1b);color:#fef2f2;'>"
        f"<div style='font-size:12px;letter-spacing:0.12em;color:#fecaca;'>{escape(_EMAIL_BRAND_NAME)}</div>"
        f"<div style='margin-top:10px;font-size:24px;font-weight:700;line-height:1.35;'>{escape(payload['title'])}</div>"
        f"<div style='margin-top:12px;display:inline-block;padding:6px 12px;border-radius:999px;background:{blocked_bg};"
        "font-size:12px;font-weight:700;'>"
        f"{blocked_label}</div>"
        "</div>"
        "<div style='padding:24px;'>"
        f"<p style='margin:0 0 16px;color:#334155;font-size:15px;line-height:1.8;'>{escape(payload['body'])}</p>"
        "<table style='width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;'>"
        f"{detail_rows}</table>"
        "<div style='margin-top:18px;padding:16px 18px;border-radius:14px;background:#fff1f2;border:1px solid #fecdd3;'>"
        "<div style='font-size:13px;font-weight:700;color:#be123c;margin-bottom:8px;'>事件摘要</div>"
        f"<div style='font-size:14px;line-height:1.8;color:#0f172a;'>{escape(summary)}</div>"
        "</div>"
        "<div style='margin-top:18px;font-size:13px;line-height:1.8;color:#64748b;'>"
        "该邮件由校园供应链 IDS 自动发送。建议尽快进入本地 IDS 控制台复核事件详情、阻断状态与请求证据。"
        "</div>"
        "</div></div></body></html>"
    )


def _dispatch_email(settings: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.get("enabled"):
        return {"channel": "email", "status": "disabled"}
    host = str(settings.get("smtp_host") or "").strip()
    to_addrs = [item.strip() for item in str(settings.get("to_addrs") or "").split(",") if item.strip()]
    if not host or not to_addrs:
        return {"channel": "email", "status": "skipped", "detail": "smtp_host or to_addrs missing"}
    msg = EmailMessage()
    msg["Subject"] = payload["title"]
    msg["From"] = _format_email_sender(settings)
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(_plain_email_content(payload))
    msg.add_alternative(_html_email_content(payload), subtype="html")
    port = int(settings.get("smtp_port") or 465)
    username = str(settings.get("username") or "").strip()
    password = str(settings.get("password") or "")
    use_ssl = bool(settings.get("use_ssl"))
    use_tls = bool(settings.get("use_tls"))
    context = ssl.create_default_context()
    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, context=context, timeout=8)
        else:
            server = smtplib.SMTP(host, port, timeout=8)
        with server:
            if use_tls and not use_ssl:
                server.starttls(context=context)
            if username:
                server.login(username, password)
            server.send_message(msg)
        return {"channel": "email", "status": "sent"}
    except Exception as exc:
        return {"channel": "email", "status": "failed", "detail": str(exc)[:240]}


def _dispatch_json_webhook(url: str, body: dict[str, Any], *, secret: str = "") -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-IDS-Webhook-Secret"] = secret
    req = urllib_request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=8) as response:
            return {"status": "sent", "http_status": int(getattr(response, "status", 200))}
    except urllib_error.HTTPError as exc:
        return {"status": "failed", "detail": f"http {exc.code}"}
    except Exception as exc:
        return {"status": "failed", "detail": str(exc)[:240]}


def _dispatch_wecom(settings: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.get("enabled"):
        return {"channel": "wecom", "status": "disabled"}
    webhook_url = str(settings.get("webhook_url") or "").strip()
    if not webhook_url:
        return {"channel": "wecom", "status": "skipped", "detail": "webhook_url missing"}
    result = _dispatch_json_webhook(
        webhook_url,
        {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    f"**{payload['title']}**\n"
                    f"> {payload['body']}\n"
                    f"> status: {payload['event']['status']} | blocked: {payload['event']['blocked']}"
                )
            },
        },
    )
    return {"channel": "wecom", **result}


def _dispatch_webhook(settings: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.get("enabled"):
        return {"channel": "webhook", "status": "disabled"}
    url = str(settings.get("url") or "").strip()
    if not url:
        return {"channel": "webhook", "status": "skipped", "detail": "url missing"}
    result = _dispatch_json_webhook(
        url,
        payload,
        secret=str(settings.get("secret") or ""),
    )
    return {"channel": "webhook", **result}


def dispatch_notifications(event_like: dict[str, Any], *, is_test: bool = False) -> dict[str, Any]:
    settings = load_notification_settings()
    payload = _build_notification_payload(event_like, is_test=is_test)
    results = [
        _dispatch_email(settings["email"], payload),
        _dispatch_wecom(settings["wecom"], payload),
        _dispatch_webhook(settings["webhook"], payload),
    ]
    return {"payload": payload, "results": results}


def serialize_notification_event(row: IDSEvent) -> dict[str, Any]:
    return {
        "id": int(row.id or 0),
        "attack_type": row.attack_type or "",
        "attack_type_label": _attack_type_label(row.attack_type),
        "client_ip": row.client_ip or "-",
        "path": row.path or "/",
        "method": row.method or "",
        "risk_score": int(row.risk_score or 0),
        "status": row.status or "new",
        "blocked": bool(row.blocked),
        "archived": bool(row.archived),
        "created_at": _format_dt(row.created_at),
        "detector_name": row.detector_name or "",
        "response_result": row.response_result or "",
        "response_detail": row.response_detail or row.review_note or row.ai_analysis or "",
        "summary": row.response_detail or row.review_note or row.ai_analysis or "",
    }


def should_auto_dispatch_notifications(event_like: dict[str, Any]) -> bool:
    risk_score = int(event_like.get("risk_score") or 0)
    archived = bool(event_like.get("archived"))
    attack_type = str(event_like.get("attack_type") or "").strip().lower()
    response_result = str(event_like.get("response_result") or "").strip().lower()
    path = str(event_like.get("path") or "").strip()
    detector_name = str(event_like.get("detector_name") or "").strip()
    is_upload_related = path in {"/api/upload", "/api/ids/detection/sample-submit"} or detector_name in {
        "upload_ai_gate",
        "upload_audit_gate",
    }
    if archived:
        return False
    if is_upload_related and (
        response_result == "quarantine"
        or attack_type == "malware"
        or risk_score >= _AUTO_NOTIFICATION_MIN_SCORE
    ):
        return True
    return risk_score >= _AUTO_NOTIFICATION_MIN_SCORE


def _dispatch_notifications_background(event_like: dict[str, Any], *, source: str) -> None:
    event_id = int(event_like.get("id") or event_like.get("event_id") or 0)
    db = SessionLocal()
    try:
        result = dispatch_notifications(event_like, is_test=False)
        statuses = ", ".join(
            f"{item.get('channel')}={item.get('status')}"
            for item in result.get("results", [])
        ) or "no_channels"
        write_audit_log(
            db,
            user_id=None,
            user_name="ids_auto_dispatch",
            user_role="system",
            action="ids_notification_dispatch_auto",
            target_type="ids_event",
            target_id=str(event_id),
            detail=f"Auto-dispatched IDS notifications via {source}: {statuses}",
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            write_audit_log(
                db,
                user_id=None,
                user_name="ids_auto_dispatch",
                user_role="system",
                action="ids_notification_dispatch_auto",
                target_type="ids_event",
                target_id=str(event_id),
                detail=f"Auto-dispatch failed unexpectedly via {source}: {str(exc)[:280]}",
            )
            db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def auto_dispatch_notifications_for_event(
    db: Session,
    event_like: dict[str, Any],
    *,
    source: str,
) -> bool:
    event_id = int(event_like.get("id") or event_like.get("event_id") or 0)
    if not event_id or not should_auto_dispatch_notifications(event_like):
        return False

    prior_attempt = (
        db.query(AuditLog.id)
        .filter(AuditLog.action == "ids_notification_dispatch_auto")
        .filter(AuditLog.target_type == "ids_event")
        .filter(AuditLog.target_id == str(event_id))
        .first()
    )
    if prior_attempt:
        return False

    allowed, reason = _claim_auto_notification_slot(event_like)
    if not allowed:
        write_audit_log(
            db,
            user_id=None,
            user_name="ids_auto_dispatch",
            user_role="system",
            action="ids_notification_dispatch_auto",
            target_type="ids_event",
            target_id=str(event_id),
            detail=f"Auto-dispatch skipped via {source}: {reason}",
        )
        db.commit()
        return False

    threading.Thread(
        target=_dispatch_notifications_background,
        args=(dict(event_like),),
        kwargs={"source": source},
        daemon=True,
    ).start()
    return True


def _load_false_positive_memory() -> list[dict[str, Any]]:
    raw = _read_json_file(_FALSE_POSITIVE_MEMORY_PATH, [])
    return raw if isinstance(raw, list) else []


def record_false_positive_learning(event: IDSEvent, *, learned_by: str, review_note: str = "") -> None:
    entries = _load_false_positive_memory()
    event_id = int(event.id or 0)
    if any(int(item.get("event_id") or 0) == event_id for item in entries):
        return
    entries.append(
        {
            "event_id": event_id,
            "attack_type": event.attack_type or "",
            "attack_type_label": _attack_type_label(event.attack_type),
            "path_prefix": _path_prefix(event.path),
            "normalized_path": _normalize_path(event.path),
            "signature_matched": event.signature_matched or "",
            "source_rule_id": event.source_rule_id or "",
            "detector_name": event.detector_name or "",
            "user_agent_family": _ua_family(event.user_agent),
            "client_ip": event.client_ip or "",
            "learned_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "learned_by": learned_by[:64],
            "review_note": review_note[:500],
        }
    )
    _write_json_file(_FALSE_POSITIVE_MEMORY_PATH, entries[-400:])


def build_false_positive_learning(db: Session, event: IDSEvent) -> dict[str, Any]:
    signals: list[dict[str, Any]] = []
    historical_rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.status == "false_positive")
        .order_by(IDSEvent.created_at.desc())
        .limit(400)
        .all()
    )
    memory_rows = _load_false_positive_memory()
    normalized_path = _normalize_path(event.path)
    path_prefix = _path_prefix(event.path)
    ua_family = _ua_family(event.user_agent)

    same_signature = [
        row for row in historical_rows
        if row.signature_matched and row.signature_matched == (event.signature_matched or "")
    ]
    if same_signature:
        signals.append(
            {
                "kind": "signature",
                "pattern": event.signature_matched or "-",
                "count": len(same_signature),
                "recommendation": "Candidate rule-tuning: tighten the signature with extra context before auto-escalation.",
                "source": "history",
            }
        )

    same_path = [
        row for row in historical_rows
        if _normalize_path(row.path) == normalized_path and row.attack_type == event.attack_type
    ]
    if same_path:
        signals.append(
            {
                "kind": "path_prefix",
                "pattern": path_prefix,
                "count": len(same_path),
                "recommendation": "Candidate whitelist review: validate whether this business path is trusted enough for scoped exceptions.",
                "source": "history",
            }
        )

    same_rule = [
        row for row in historical_rows
        if row.source_rule_id and row.source_rule_id == (event.source_rule_id or "")
    ]
    if same_rule:
        signals.append(
            {
                "kind": "rule",
                "pattern": event.source_rule_id or "-",
                "count": len(same_rule),
                "recommendation": "Candidate rule revision: reduce weight or require an additional indicator before scoring high risk.",
                "source": "history",
            }
        )

    memory_matches = [
        row for row in memory_rows
        if row.get("normalized_path") == normalized_path
        or row.get("signature_matched") == (event.signature_matched or "")
        or row.get("user_agent_family") == ua_family
    ]
    if memory_matches:
        signals.append(
            {
                "kind": "memory",
                "pattern": normalized_path,
                "count": len(memory_matches),
                "recommendation": "Prior operator reviews already marked similar traffic as false positive. Compare this event before escalating.",
                "source": "memory",
            }
        )

    top_signal = max(signals, key=lambda item: int(item["count"]), default=None)
    recommendation = (
        top_signal["recommendation"]
        if top_signal
        else "No strong false-positive pattern yet. Keep it blocked until an operator review confirms the traffic is trusted."
    )
    return {
        "matched_learning_events": sum(int(item["count"]) for item in signals),
        "signals": sorted(signals, key=lambda item: int(item["count"]), reverse=True)[:4],
        "recommendation": recommendation,
        "last_learned_at": memory_matches[0]["learned_at"] if memory_matches else None,
    }


def build_event_profile(db: Session, event: IDSEvent) -> dict[str, Any]:
    rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.client_ip == event.client_ip)
        .order_by(IDSEvent.created_at.desc())
        .limit(120)
        .all()
    )
    if not rows:
        return {
            "client_ip": event.client_ip or "-",
            "source_location": _derive_location_from_ip(event.client_ip),
            "user_agent_family": _ua_family(event.user_agent),
            "user_agent_sample": event.user_agent or "-",
            "total_events_from_ip": 0,
            "blocked_events_from_ip": 0,
            "high_risk_events_from_ip": 0,
            "first_seen_at": None,
            "last_seen_at": None,
            "distinct_attack_types": [],
            "top_paths": [],
            "historical_behaviors": [],
        }

    ascending = list(reversed(rows))
    path_counts = Counter(_path_prefix(row.path) for row in rows if row.path)
    behavior_counts = Counter(_attack_type_label(row.attack_type) for row in rows)
    return {
        "client_ip": event.client_ip or "-",
        "source_location": _derive_location_from_ip(event.client_ip),
        "user_agent_family": _ua_family(event.user_agent or rows[0].user_agent),
        "user_agent_sample": (event.user_agent or rows[0].user_agent or "")[:220],
        "total_events_from_ip": len(rows),
        "blocked_events_from_ip": sum(1 for row in rows if int(row.blocked or 0) == 1),
        "high_risk_events_from_ip": sum(1 for row in rows if int(row.risk_score or 0) >= 80),
        "first_seen_at": _format_dt(ascending[0].created_at if ascending else None),
        "last_seen_at": _format_dt(rows[0].created_at),
        "distinct_attack_types": sorted({_attack_type_label(row.attack_type) for row in rows if row.attack_type})[:8],
        "top_paths": [{"path": path, "count": count} for path, count in path_counts.most_common(5)],
        "historical_behaviors": [{"label": label, "count": count} for label, count in behavior_counts.most_common(5)],
    }


def build_event_timeline(db: Session, event: IDSEvent) -> dict[str, Any]:
    use_correlation = bool(event.correlation_key)
    base_query = db.query(IDSEvent).order_by(IDSEvent.created_at.asc(), IDSEvent.id.asc())
    if use_correlation:
        correlated = base_query.filter(IDSEvent.correlation_key == event.correlation_key).limit(24).all()
        if len(correlated) >= 2:
            return {
                "basis": "correlation_key",
                "anchor_value": event.correlation_key or "",
                "total": len(correlated),
                "items": [_serialize_mini_event(row) for row in correlated],
            }
    rows = (
        base_query
        .filter(IDSEvent.client_ip == event.client_ip)
        .limit(24)
        .all()
    )
    return {
        "basis": "client_ip",
        "anchor_value": event.client_ip or "",
        "total": len(rows),
        "items": [_serialize_mini_event(row) for row in rows],
    }


def build_event_cluster(db: Session, event: IDSEvent) -> dict[str, Any]:
    rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.attack_type == event.attack_type)
        .order_by(IDSEvent.created_at.desc())
        .limit(200)
        .all()
    )
    normalized_path = _normalize_path(event.path)
    signature = event.signature_matched or ""
    cluster_rows = [
        row for row in rows
        if _normalize_path(row.path) == normalized_path
        or (signature and row.signature_matched == signature)
    ]
    summary = (
        f"{_attack_type_label(event.attack_type)} clustered around {normalized_path}"
        if cluster_rows
        else f"{_attack_type_label(event.attack_type)} has no recent cluster"
    )
    return {
        "cluster_key": f"{event.attack_type}|{normalized_path}|{signature or '-'}",
        "summary": summary,
        "total": len(cluster_rows),
        "same_attack_type_total": len(rows),
        "same_signature_total": sum(1 for row in rows if signature and row.signature_matched == signature),
        "same_path_total": sum(1 for row in rows if _normalize_path(row.path) == normalized_path),
        "recent_items": [_serialize_mini_event(row) for row in cluster_rows[:8]],
    }


def build_attack_heatboard(db: Session) -> dict[str, Any]:
    now = datetime.utcnow()
    day_start = datetime(now.year, now.month, now.day)
    today_rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.created_at >= day_start)
        .order_by(IDSEvent.created_at.desc())
        .all()
    )
    hourly = [{"hour": f"{hour:02d}", "total": 0, "high_risk": 0} for hour in range(24)]
    type_counts: Counter[str] = Counter()
    ip_counts: Counter[str] = Counter()
    for row in today_rows:
        if row.created_at:
            hour = row.created_at.hour
            hourly[hour]["total"] += 1
            if int(row.risk_score or 0) >= 80:
                hourly[hour]["high_risk"] += 1
        type_counts[_attack_type_label(row.attack_type)] += 1
        if row.client_ip:
            ip_counts[row.client_ip] += 1

    trend_start = day_start - timedelta(days=6)
    trend_rows = (
        db.query(IDSEvent)
        .filter(IDSEvent.created_at >= trend_start)
        .filter(IDSEvent.risk_score >= 80)
        .all()
    )
    trend_counts: dict[str, int] = defaultdict(int)
    for row in trend_rows:
        if row.created_at:
            trend_counts[row.created_at.strftime("%Y-%m-%d")] += 1
    high_risk_trend = []
    for offset in range(7):
        date_key = (trend_start + timedelta(days=offset)).strftime("%Y-%m-%d")
        high_risk_trend.append({"date": date_key, "count": trend_counts.get(date_key, 0)})

    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "today_total": len(today_rows),
        "today_high_risk_total": sum(1 for row in today_rows if int(row.risk_score or 0) >= 80),
        "today_blocked_total": sum(1 for row in today_rows if int(row.blocked or 0) == 1),
        "by_type": [{"attack_type_label": label, "count": count} for label, count in type_counts.most_common(6)],
        "hourly": hourly,
        "high_risk_trend": high_risk_trend,
        "hot_ips": [{"client_ip": ip, "count": count} for ip, count in ip_counts.most_common(5)],
    }


def build_event_insight(db: Session, event: IDSEvent) -> dict[str, Any]:
    return {
        "profile": build_event_profile(db, event),
        "timeline": build_event_timeline(db, event),
        "cluster": build_event_cluster(db, event),
        "false_positive_learning": build_false_positive_learning(db, event),
    }
