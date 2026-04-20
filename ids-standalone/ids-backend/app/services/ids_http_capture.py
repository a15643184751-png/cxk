from __future__ import annotations

from http import HTTPStatus
from typing import Iterable

from sqlalchemy.orm import Session

from ..config import settings
from ..models.ids_http_session import IDSHTTPSession

_TEXTUAL_CONTENT_TYPES = (
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-www-form-urlencoded",
    "image/svg+xml",
    "text/",
)


def normalize_ip(value: str) -> str:
    return str(value or "").strip().replace("::ffff:", "").split("%", 1)[0][:64]


def request_target(path: str, query: str) -> str:
    return f"{path}?{query}" if query else path


def format_header_lines(headers: Iterable[tuple[str, str]]) -> str:
    return "\r\n".join(f"{name}: {value}" for name, value in headers if name)


def _decode_bytes(data: bytes, content_type: str) -> str:
    cap = max(512, int(settings.IDS_GATEWAY_MAX_CAPTURE_BYTES or 24576))
    sample = data[:cap]
    if not sample:
        return ""

    normalized_content_type = str(content_type or "").lower()
    if any(token in normalized_content_type for token in _TEXTUAL_CONTENT_TYPES):
        for encoding in ("utf-8", "gb18030", "latin-1"):
            try:
                return sample.decode(encoding)
            except UnicodeDecodeError:
                continue
        return sample.decode("utf-8", errors="ignore")

    return f"<binary {len(data)} bytes; content-type={content_type or 'unknown'}>"


def build_raw_request(method: str, target: str, headers: Iterable[tuple[str, str]], body_bytes: bytes) -> tuple[str, str]:
    header_lines = format_header_lines(headers)
    body_text = _decode_bytes(body_bytes, next((value for name, value in headers if name.lower() == "content-type"), ""))
    raw = f"{method.upper()} {target} HTTP/1.1\r\n{header_lines}\r\n\r\n{body_text}".strip()
    return raw, body_text


def build_raw_response(status_code: int, headers: Iterable[tuple[str, str]], body_bytes: bytes) -> tuple[str, str]:
    header_lines = format_header_lines(headers)
    content_type = next((value for name, value in headers if name.lower() == "content-type"), "")
    body_text = _decode_bytes(body_bytes, content_type)
    try:
        reason = HTTPStatus(status_code).phrase
    except ValueError:
        reason = "Unknown"
    raw = f"HTTP/1.1 {status_code} {reason}\r\n{header_lines}\r\n\r\n{body_text}".strip()
    return raw, body_text


def save_http_session(
    db: Session,
    *,
    client_ip: str,
    scheme: str,
    host: str,
    method: str,
    path: str,
    query_string: str,
    route_kind: str,
    upstream_base: str,
    upstream_url: str,
    user_agent: str,
    request_headers: str,
    request_body: str,
    raw_request: str,
    request_size: int,
    response_status: int,
    response_headers: str,
    response_body: str,
    raw_response: str,
    response_size: int,
    content_type: str,
    duration_ms: int,
    blocked: bool,
    attack_type: str = "",
    risk_score: int = 0,
    confidence: int = 0,
    incident_id: int | None = None,
    response_note: str = "",
) -> int:
    record = IDSHTTPSession(
        client_ip=normalize_ip(client_ip),
        scheme=(scheme or "http")[:16],
        host=(host or "")[:255],
        method=(method or "")[:16].upper(),
        path=(path or "")[:1024],
        query_string=query_string or "",
        route_kind=(route_kind or "frontend")[:32],
        upstream_base=(upstream_base or "")[:255],
        upstream_url=(upstream_url or "")[:1024],
        user_agent=(user_agent or "")[:512],
        request_headers=request_headers or "",
        request_body=request_body or "",
        raw_request=raw_request or "",
        request_size=max(0, int(request_size or 0)),
        response_status=max(0, int(response_status or 0)),
        response_headers=response_headers or "",
        response_body=response_body or "",
        raw_response=raw_response or "",
        response_size=max(0, int(response_size or 0)),
        content_type=(content_type or "")[:255],
        duration_ms=max(0, int(duration_ms or 0)),
        blocked=1 if blocked else 0,
        attack_type=(attack_type or "")[:64],
        risk_score=max(0, int(risk_score or 0)),
        confidence=max(0, int(confidence or 0)),
        incident_id=incident_id,
        response_note=response_note or "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return int(record.id)
