from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger("ids.standalone")


def standalone_ids_enabled() -> bool:
    return bool(
        settings.IDS_STANDALONE_ENABLED
        and (settings.IDS_STANDALONE_BASE_URL or "").strip()
    )


def _base_url() -> str:
    return str(settings.IDS_STANDALONE_BASE_URL or "").rstrip("/")


def _source_system() -> str:
    return (settings.IDS_STANDALONE_SOURCE_SYSTEM or "campus_supply_chain_site").strip()[:64]


def _headers(client_ip: str = "", user_agent: str = "") -> dict[str, str]:
    headers = {
        "X-IDS-Source-System": _source_system(),
    }
    token = str(settings.IDS_STANDALONE_INTEGRATION_TOKEN or "").strip()
    if token:
        headers["X-IDS-Integration-Token"] = token
    if client_ip:
        headers["X-Forwarded-For"] = client_ip[:128]
    if user_agent:
        headers["User-Agent"] = user_agent[:512]
    return headers


def _candidate_base_urls() -> list[str]:
    base_url = _base_url()
    if not base_url:
        return []
    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").strip().lower()
    candidates = [base_url]
    host_variants: list[str] = []
    if host == "127.0.0.1":
        host_variants.append("localhost")
    elif host == "localhost":
        host_variants.append("127.0.0.1")
    for variant in host_variants:
        netloc = variant
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        alt = urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)).rstrip("/")
        if alt not in candidates:
            candidates.append(alt)
    return candidates


def _ingest_timeout() -> httpx.Timeout:
    base = max(8.0, float(settings.IDS_STANDALONE_TIMEOUT_SECONDS or 8.0))
    return httpx.Timeout(connect=min(base, 5.0), read=base, write=base, pool=min(base, 5.0))


def _upload_timeout() -> httpx.Timeout:
    base = max(20.0, float(settings.IDS_STANDALONE_TIMEOUT_SECONDS or 8.0))
    return httpx.Timeout(connect=min(base, 6.0), read=max(base, 45.0), write=max(base, 45.0), pool=min(base, 6.0))


def _response_payload(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        data = response.text
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("reason") or detail)[:300]
        if detail:
            return str(detail)[:300]
        return str(data)[:300]
    return str(data or response.text or "")[:300]


async def _post_with_retries(
    *,
    endpoint: str,
    client_ip: str,
    user_agent: str,
    timeout: httpx.Timeout,
    json_payload: dict[str, Any] | None = None,
    file_payload: dict[str, tuple[str, bytes, str]] | None = None,
) -> dict[str, Any]:
    last_error = "bridge_unavailable"
    for base_url in _candidate_base_urls():
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.post(
                    f"{base_url}{endpoint}",
                    json=json_payload,
                    files=file_payload,
                    headers=_headers(client_ip=client_ip, user_agent=user_agent),
                )
            if response.is_success:
                payload = response.json()
                return {"ok": True, "data": payload, "base_url": base_url}
            last_error = f"http {response.status_code}: {_response_payload(response)}"
            logger.warning("standalone IDS request failed via %s%s: %s", base_url, endpoint, last_error)
        except Exception as exc:
            detail = str(exc).strip()
            last_error = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
            logger.warning("standalone IDS request failed via %s%s: %s", base_url, endpoint, last_error)
    return {"ok": False, "reason": last_error}


def _severity_from_score(risk_score: int) -> str:
    if risk_score >= 70:
        return "high"
    if risk_score >= 40:
        return "medium"
    return "low"


def _event_fingerprint(client_ip: str, method: str, path: str, attack_type: str, signature: str) -> str:
    return "::".join(
        [
            (client_ip or "").strip(),
            (method or "").strip().upper(),
            (path or "").strip(),
            (attack_type or "").strip(),
            (signature or "").strip()[:64],
        ]
    )[:255]


def _correlation_key(occurred_at: datetime, client_ip: str, attack_type: str) -> str:
    return "::".join(
        [
            occurred_at.strftime("%Y%m%d%H%M"),
            (client_ip or "").strip(),
            (attack_type or "").strip(),
            "campus_site_runtime_probe",
        ]
    )[:255]


async def ingest_runtime_detection(
    *,
    client_ip: str,
    method: str,
    path: str,
    query: str,
    body_snippet: str,
    user_agent: str,
    headers_snippet: str,
    attack_type: str,
    signature_matched: str,
    risk_score: int,
    confidence: int,
    blocked: bool,
    action_taken: str = "",
    firewall_rule: str = "",
) -> dict[str, Any]:
    if not standalone_ids_enabled():
        return {"ok": False, "reason": "disabled"}

    occurred_at = datetime.now(timezone.utc)
    evidence_summary = (
        f"Campus site runtime probe matched {attack_type} on {method.upper()} {path}. "
        f"blocked={'yes' if blocked else 'no'}; score={risk_score}; confidence={confidence}."
    )[:500]
    payload = {
        "event_origin": "real",
        "source_classification": "custom_project",
        "detector_family": "site_runtime",
        "detector_name": "campus_site_runtime_probe",
        "rule_id": (signature_matched or attack_type or "site_runtime_rule")[:128],
        "rule_name": (attack_type or "site_runtime_detection")[:128],
        "source_version": "campus-site-inline-ids",
        "source_freshness": "current",
        "occurred_at": occurred_at.isoformat(),
        "client_ip": (client_ip or "0.0.0.0")[:64],
        "asset_ref": (path or "")[:512],
        "attack_type": (attack_type or "unknown")[:64],
        "severity": _severity_from_score(int(risk_score or 0)),
        "confidence": max(0, min(100, int(confidence or 0))),
        "blocked": bool(blocked),
        "action_taken": (action_taken or "")[:128],
        "response_result": "success" if blocked else "record_only",
        "firewall_rule": (firewall_rule or "")[:256],
        "event_fingerprint": _event_fingerprint(client_ip, method, path, attack_type, signature_matched),
        "correlation_key": _correlation_key(occurred_at, client_ip, attack_type),
        "evidence_summary": evidence_summary,
        "raw_evidence": {
            "method": (method or "").upper()[:16],
            "path": (path or "")[:512],
            "query_snippet": (query or "")[:500],
            "body_snippet": (body_snippet or "")[:500],
            "user_agent": (user_agent or "")[:512],
            "headers_snippet": (headers_snippet or "")[:1000],
        },
    }

    return await _post_with_retries(
        endpoint="/api/ids/events/ingest",
        client_ip=client_ip,
        user_agent=user_agent,
        timeout=_ingest_timeout(),
        json_payload=payload,
    )


async def submit_upload_to_standalone(
    *,
    file_name: str,
    content: bytes,
    client_ip: str,
    user_agent: str,
) -> dict[str, Any]:
    if not standalone_ids_enabled():
        return {"ok": False, "reason": "disabled"}

    files = {
        "file": (
            file_name,
            content,
            "application/octet-stream",
        )
    }

    result = await _post_with_retries(
        endpoint="/api/upload",
        client_ip=client_ip,
        user_agent=user_agent,
        timeout=_upload_timeout(),
        file_payload=files,
    )
    if result.get("ok"):
        payload = result.get("data")
        if isinstance(payload, dict):
            payload["via_ids_standalone"] = True
    return result
