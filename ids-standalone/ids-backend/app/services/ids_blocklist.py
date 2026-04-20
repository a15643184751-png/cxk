"""Application-layer IP blocklist helpers for IDS manual blocking."""
from __future__ import annotations

import ipaddress
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings

_BLOCKLIST_LOCK = threading.Lock()
_BLOCKLIST_PATH = Path(settings.IDS_OPERATOR_STATE_DIR) / "blocked_ips.json"


def _blocklist_path() -> Path:
    _BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _BLOCKLIST_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ip(ip: str) -> tuple[str | None, str | None]:
    value = (ip or "").strip()
    if not value:
        return None, "missing IP address"
    if value.lower() == "localhost":
        return None, "localhost cannot be blocked"
    if "%" in value and ":" in value:
        value = value.split("%", 1)[0]
    try:
        normalized = ipaddress.ip_address(value).compressed
    except ValueError:
        return None, f"invalid IP address: {value}"
    if normalized in {"127.0.0.1", "::1"}:
        return None, "loopback address cannot be blocked"
    return normalized, None


def _load_state() -> dict[str, Any]:
    path = _blocklist_path()
    if not path.exists():
        return {"items": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}
    items = raw.get("items")
    if not isinstance(items, list):
        return {"items": []}
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ip = str(item.get("ip") or "").strip()
        if not ip:
            continue
        normalized_items.append(item)
    return {"items": normalized_items}


def _write_state(state: dict[str, Any]) -> None:
    path = _blocklist_path()
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def is_ip_blocked(ip: str) -> bool:
    normalized, error = _normalize_ip(ip)
    if error or not normalized:
        return False
    with _BLOCKLIST_LOCK:
        state = _load_state()
        return any(str(item.get("ip") or "") == normalized for item in state.get("items", []))


def list_blocked_ips() -> list[dict[str, Any]]:
    with _BLOCKLIST_LOCK:
        state = _load_state()
        items = [dict(item) for item in state.get("items", []) if isinstance(item, dict)]

    items.sort(
        key=lambda item: str(item.get("updated_at") or item.get("blocked_at") or ""),
        reverse=True,
    )
    return items


def get_blocked_ip(ip: str) -> dict[str, Any] | None:
    normalized, error = _normalize_ip(ip)
    if error or not normalized:
        return None

    with _BLOCKLIST_LOCK:
        state = _load_state()
        for item in state.get("items", []):
            if str(item.get("ip") or "") == normalized:
                return dict(item)
    return None


def add_blocked_ip(
    ip: str,
    *,
    source: str = "manual_block",
    event_id: int | None = None,
    actor: str = "system",
    note: str | None = None,
) -> tuple[bool, str]:
    normalized, error = _normalize_ip(ip)
    if error or not normalized:
        return False, error or "invalid IP address"

    now = _now_iso()
    with _BLOCKLIST_LOCK:
        state = _load_state()
        items = state.setdefault("items", [])
        for item in items:
            if str(item.get("ip") or "") != normalized:
                continue
            item["updated_at"] = now
            item["source"] = source
            if event_id is not None:
                item["event_id"] = event_id
            if actor:
                item["actor"] = actor
            if note is not None:
                item["note"] = str(note or "")[:200]
            _write_state(state)
            return True, f"{normalized} already exists in application blocklist"

        entry: dict[str, Any] = {
            "ip": normalized,
            "source": source,
            "blocked_at": now,
            "updated_at": now,
        }
        if event_id is not None:
            entry["event_id"] = event_id
        if actor:
            entry["actor"] = actor
        if note is not None:
            entry["note"] = str(note or "")[:200]
        items.append(entry)
        _write_state(state)
    return True, f"{normalized} added to application blocklist"


def remove_blocked_ip(ip: str) -> tuple[bool, str]:
    normalized, error = _normalize_ip(ip)
    if error or not normalized:
        return False, error or "invalid IP address"

    with _BLOCKLIST_LOCK:
        state = _load_state()
        items = state.get("items", [])
        remaining = [item for item in items if str(item.get("ip") or "") != normalized]
        if len(remaining) == len(items):
            return True, f"{normalized} was not present in application blocklist"
        state["items"] = remaining
        _write_state(state)
    return True, f"{normalized} removed from application blocklist"
