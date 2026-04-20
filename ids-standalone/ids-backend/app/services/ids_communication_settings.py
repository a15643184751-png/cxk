from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..config import settings

_APP_ROOT = Path(__file__).resolve().parents[2]
_STATE_DIR = Path(settings.IDS_OPERATOR_STATE_DIR)
_COMMUNICATION_SETTINGS_PATH = _STATE_DIR / "communication_settings.json"
_ENV_PATH = _APP_ROOT / ".env"
_DISPLAY_LEGACY_ALIASES = {
    "边界演示链路": "边界访问链路",
    "实训演示单元": "实训协同单元",
    "演示时钟": "巡检时钟",
    "总控大屏": "总控视图",
}


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


def _normalize_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    return text[:128] if text else fallback


def _normalize_display_text(value: Any, fallback: str) -> str:
    text = _normalize_text(value, fallback)
    return _DISPLAY_LEGACY_ALIASES.get(text, text)


def _normalize_port(value: Any, fallback: int) -> int:
    try:
        port = int(value)
    except Exception:
        return fallback
    if 1 <= port <= 65535:
        return port
    return fallback


def _split_host_port(url: str, fallback_port: int) -> tuple[str, int]:
    raw = str(url or "").strip()
    if not raw:
        return "", fallback_port
    try:
        parsed = urlsplit(raw)
    except Exception:
        return "", fallback_port
    host = str(parsed.hostname or "").strip()
    port = int(parsed.port or fallback_port)
    return host, port


def _read_env_values() -> dict[str, str]:
    env_values: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return env_values
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env_values[key.strip()] = value.strip().strip('"').strip("'")
    return env_values


def _write_env_values(updates: dict[str, str]) -> None:
    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
    written_keys: set[str] = set()
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            next_lines.append(line)
            continue
        key, _ = line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key in updates:
            next_lines.append(f"{normalized_key}={updates[normalized_key]}")
            written_keys.add(normalized_key)
        else:
            next_lines.append(line)
    for key, value in updates.items():
        if key not in written_keys:
            next_lines.append(f"{key}={value}")
    _ENV_PATH.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")


def _default_payload() -> dict[str, Any]:
    frontend_ip, frontend_port = _split_host_port(settings.IDS_GATEWAY_FRONTEND_BASE_URL, 5173)
    backend_ip, backend_port = _split_host_port(settings.IDS_GATEWAY_BACKEND_BASE_URL, 8166)
    return {
        "real": {
            "gateway_port": int(settings.IDS_GATEWAY_DEFAULT_PORT or 8188),
            "frontend_ip": frontend_ip or "10.134.32.153",
            "frontend_port": frontend_port,
            "backend_ip": backend_ip or frontend_ip or "10.134.32.153",
            "backend_port": backend_port,
        },
        "display": {
            "site_label": "校园供应链主站",
            "domain_code": "Campus-Link-A",
            "link_template": "教学业务链路",
            "routing_profile": "双向会话镜像",
            "packet_profile": "HTTP 会话包",
            "signal_band": "基础频段",
            "coordination_group": "校内联防单元",
            "display_mode": "总控视图",
            "session_track_mode": "连续轮转",
            "trace_color_mode": "分层染色",
            "link_sync_clock": "边界同步时钟",
            "relay_group": "north-gateway",
            "auto_rotate": True,
            "popup_broadcast": True,
            "packet_shadow": True,
            "link_keepalive": True,
        },
        "updated_at": None,
    }


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    defaults = _default_payload()
    incoming_real = payload.get("real") if isinstance(payload.get("real"), dict) else {}
    incoming_display = payload.get("display") if isinstance(payload.get("display"), dict) else {}
    normalized = {
        "real": {
            "gateway_port": _normalize_port(
                incoming_real.get("gateway_port"),
                defaults["real"]["gateway_port"],
            ),
            "frontend_ip": _normalize_text(
                incoming_real.get("frontend_ip"),
                defaults["real"]["frontend_ip"],
            ),
            "frontend_port": _normalize_port(
                incoming_real.get("frontend_port"),
                defaults["real"]["frontend_port"],
            ),
            "backend_ip": _normalize_text(
                incoming_real.get("backend_ip"),
                defaults["real"]["backend_ip"],
            ),
            "backend_port": _normalize_port(
                incoming_real.get("backend_port"),
                defaults["real"]["backend_port"],
            ),
        },
        "display": {
            "site_label": _normalize_display_text(incoming_display.get("site_label"), defaults["display"]["site_label"]),
            "domain_code": _normalize_display_text(incoming_display.get("domain_code"), defaults["display"]["domain_code"]),
            "link_template": _normalize_display_text(incoming_display.get("link_template"), defaults["display"]["link_template"]),
            "routing_profile": _normalize_display_text(incoming_display.get("routing_profile"), defaults["display"]["routing_profile"]),
            "packet_profile": _normalize_display_text(incoming_display.get("packet_profile"), defaults["display"]["packet_profile"]),
            "signal_band": _normalize_display_text(incoming_display.get("signal_band"), defaults["display"]["signal_band"]),
            "coordination_group": _normalize_display_text(incoming_display.get("coordination_group"), defaults["display"]["coordination_group"]),
            "display_mode": _normalize_display_text(incoming_display.get("display_mode"), defaults["display"]["display_mode"]),
            "session_track_mode": _normalize_display_text(incoming_display.get("session_track_mode"), defaults["display"]["session_track_mode"]),
            "trace_color_mode": _normalize_display_text(incoming_display.get("trace_color_mode"), defaults["display"]["trace_color_mode"]),
            "link_sync_clock": _normalize_display_text(incoming_display.get("link_sync_clock"), defaults["display"]["link_sync_clock"]),
            "relay_group": _normalize_display_text(incoming_display.get("relay_group"), defaults["display"]["relay_group"]),
            "auto_rotate": bool(incoming_display.get("auto_rotate", defaults["display"]["auto_rotate"])),
            "popup_broadcast": bool(incoming_display.get("popup_broadcast", defaults["display"]["popup_broadcast"])),
            "packet_shadow": bool(incoming_display.get("packet_shadow", defaults["display"]["packet_shadow"])),
            "link_keepalive": bool(incoming_display.get("link_keepalive", defaults["display"]["link_keepalive"])),
        },
        "updated_at": str(payload.get("updated_at") or "") or None,
    }
    return normalized


def _with_derived(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    real = normalized["real"]
    frontend_url = f"http://{real['frontend_ip']}:{real['frontend_port']}"
    backend_url = f"http://{real['backend_ip']}:{real['backend_port']}"
    return {
        **normalized,
        "derived": {
            "frontend_upstream_url": frontend_url,
            "backend_upstream_url": backend_url,
            "gateway_port": int(real["gateway_port"]),
            "restart_required": True,
            "effective_scope": "gateway_port_and_upstream_ip_port_only",
            "effective_hint": "当前保存会更新网关入口与业务回源地址，重启 IDS Gateway 后应用到转发链路。",
            "env_path": str(_ENV_PATH),
        },
    }


def load_communication_settings() -> dict[str, Any]:
    defaults = _default_payload()
    stored = _read_json_file(_COMMUNICATION_SETTINGS_PATH, defaults)
    merged = _normalize_payload(stored if isinstance(stored, dict) else defaults)

    env_values = _read_env_values()
    frontend_ip, frontend_port = _split_host_port(
        env_values.get("IDS_GATEWAY_FRONTEND_BASE_URL", settings.IDS_GATEWAY_FRONTEND_BASE_URL),
        merged["real"]["frontend_port"],
    )
    backend_ip, backend_port = _split_host_port(
        env_values.get("IDS_GATEWAY_BACKEND_BASE_URL", settings.IDS_GATEWAY_BACKEND_BASE_URL),
        merged["real"]["backend_port"],
    )

    merged["real"]["gateway_port"] = _normalize_port(
        env_values.get("IDS_GATEWAY_DEFAULT_PORT"),
        merged["real"]["gateway_port"],
    )
    if frontend_ip:
        merged["real"]["frontend_ip"] = frontend_ip
    merged["real"]["frontend_port"] = _normalize_port(frontend_port, merged["real"]["frontend_port"])
    if backend_ip:
        merged["real"]["backend_ip"] = backend_ip
    merged["real"]["backend_port"] = _normalize_port(backend_port, merged["real"]["backend_port"])
    return _with_derived(merged)


def save_communication_settings(payload: dict[str, Any]) -> dict[str, Any]:
    current = load_communication_settings()
    merged = _normalize_payload(
        {
            "real": {**current.get("real", {}), **(payload.get("real") or {})},
            "display": {**current.get("display", {}), **(payload.get("display") or {})},
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

    frontend_url = f"http://{merged['real']['frontend_ip']}:{merged['real']['frontend_port']}"
    backend_url = f"http://{merged['real']['backend_ip']}:{merged['real']['backend_port']}"

    _write_json_file(_COMMUNICATION_SETTINGS_PATH, merged)
    _write_env_values(
        {
            "IDS_GATEWAY_DEFAULT_PORT": str(merged["real"]["gateway_port"]),
            "IDS_GATEWAY_FRONTEND_BASE_URL": frontend_url,
            "IDS_GATEWAY_BACKEND_BASE_URL": backend_url,
        }
    )

    settings.IDS_GATEWAY_DEFAULT_PORT = int(merged["real"]["gateway_port"])
    settings.IDS_GATEWAY_FRONTEND_BASE_URL = frontend_url
    settings.IDS_GATEWAY_BACKEND_BASE_URL = backend_url
    return _with_derived(merged)
