from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel

from ..config import GatewayPortMapping, GatewaySiteMapping, settings

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


def _normalize_bool(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return fallback


def _normalize_hosts(value: Any) -> list[str]:
    if value is None:
        return []
    raw_items = value.split(",") if isinstance(value, str) else list(value)
    hosts: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        host = str(item or "").strip().lower().rstrip(".")
        if not host or host in seen:
            continue
        seen.add(host)
        hosts.append(host)
    return hosts[:12]


def _sanitize_url(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if "://" not in raw:
        raw = f"http://{raw}"
    try:
        parsed = urlsplit(raw)
    except Exception:
        return fallback
    if parsed.scheme not in {"http", "https"}:
        return fallback
    if not parsed.hostname:
        return fallback
    netloc = parsed.netloc.rstrip("/")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{netloc}{path}"


def _split_host_port(url: str, fallback_port: int) -> tuple[str, int]:
    raw = str(url or "").strip()
    if not raw:
        return "", fallback_port
    try:
        parsed = urlsplit(raw if "://" in raw else f"http://{raw}")
    except Exception:
        return "", fallback_port
    host = str(parsed.hostname or "").strip()
    port = int(parsed.port or fallback_port)
    return host, port


def _build_upstream_url(host: str, port: int) -> str:
    normalized_host = str(host or "").strip()
    if not normalized_host:
        return ""
    return f"http://{normalized_host}:{int(port)}"


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


def _coerce_mapping_item(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump()
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return value.model_dump()
        except Exception:
            return None
    return None


def _coerce_mapping_list(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    normalized: list[dict[str, Any]] = []
    for item in items:
        mapping = _coerce_mapping_item(item)
        if mapping:
            normalized.append(mapping)
    return normalized


def _default_payload() -> dict[str, Any]:
    frontend_ip, frontend_port = _split_host_port(settings.IDS_GATEWAY_FRONTEND_BASE_URL, 5173)
    backend_ip, backend_port = _split_host_port(settings.IDS_GATEWAY_BACKEND_BASE_URL, 8166)
    return {
        "real": {
            "gateway_port": int(settings.IDS_GATEWAY_DEFAULT_PORT or 8188),
            "frontend_ip": frontend_ip or "127.0.0.1",
            "frontend_port": frontend_port,
            "backend_ip": backend_ip or frontend_ip or "127.0.0.1",
            "backend_port": backend_port,
            "default_site_key": "campus_supply_chain",
            "default_site_name": "校园供应链",
            "extra_port_sites": [],
            "host_sites": [],
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


def _normalize_port_site(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    frontend_upstream = _sanitize_url(item.get("frontend_upstream"), "")
    backend_upstream = _sanitize_url(item.get("backend_upstream"), "")
    if not frontend_upstream or not backend_upstream:
        return None
    return {
        "site_key": _normalize_text(item.get("site_key"), "site"),
        "display_name": _normalize_text(item.get("display_name"), "未命名入口"),
        "ingress_port": _normalize_port(item.get("ingress_port"), 8288),
        "frontend_upstream": frontend_upstream,
        "backend_upstream": backend_upstream,
    }


def _normalize_host_site(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    hosts = _normalize_hosts(item.get("hosts"))
    frontend_upstream = _sanitize_url(item.get("frontend_upstream"), "")
    backend_upstream = _sanitize_url(item.get("backend_upstream"), "")
    if not hosts or not frontend_upstream or not backend_upstream:
        return None
    return {
        "site_key": _normalize_text(item.get("site_key"), "site"),
        "display_name": _normalize_text(item.get("display_name"), "未命名域名入口"),
        "hosts": hosts,
        "frontend_upstream": frontend_upstream,
        "backend_upstream": backend_upstream,
    }


def _normalize_port_sites(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen_ports: set[int] = set()
    for item in items:
        row = _normalize_port_site(item)
        if not row:
            continue
        ingress_port = int(row["ingress_port"])
        if ingress_port in seen_ports:
            continue
        seen_ports.add(ingress_port)
        normalized.append(row)
    return normalized[:12]


def _normalize_host_sites(value: Any) -> list[dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in items:
        row = _normalize_host_site(item)
        if not row:
            continue
        dedupe_key = f"{row['site_key']}|{','.join(row['hosts'])}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        normalized.append(row)
    return normalized[:12]


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
            "default_site_key": _normalize_text(
                incoming_real.get("default_site_key"),
                defaults["real"]["default_site_key"],
            ),
            "default_site_name": _normalize_text(
                incoming_real.get("default_site_name"),
                defaults["real"]["default_site_name"],
            ),
            "extra_port_sites": _normalize_port_sites(incoming_real.get("extra_port_sites")),
            "host_sites": _normalize_host_sites(incoming_real.get("host_sites")),
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
            "auto_rotate": _normalize_bool(incoming_display.get("auto_rotate"), defaults["display"]["auto_rotate"]),
            "popup_broadcast": _normalize_bool(incoming_display.get("popup_broadcast"), defaults["display"]["popup_broadcast"]),
            "packet_shadow": _normalize_bool(incoming_display.get("packet_shadow"), defaults["display"]["packet_shadow"]),
            "link_keepalive": _normalize_bool(incoming_display.get("link_keepalive"), defaults["display"]["link_keepalive"]),
        },
        "updated_at": str(payload.get("updated_at") or "") or None,
    }
    return normalized


def _port_map_from_runtime(port_sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "site_key": item["site_key"],
            "display_name": item["display_name"],
            "ingress_port": int(item["ingress_port"]),
            "frontend_base_url": item["frontend_upstream"],
            "backend_base_url": item["backend_upstream"],
        }
        for item in port_sites
    ]


def _site_map_from_runtime(host_sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "site_key": item["site_key"],
            "display_name": item["display_name"],
            "hosts": item["hosts"],
            "frontend_base_url": item["frontend_upstream"],
            "backend_base_url": item["backend_upstream"],
        }
        for item in host_sites
    ]


def _runtime_port_sites_from_env(value: Any) -> list[dict[str, Any]]:
    rows = _coerce_mapping_list(value)
    normalized: list[dict[str, Any]] = []
    for item in rows:
        normalized_item = _normalize_port_site(
            {
                "site_key": item.get("site_key"),
                "display_name": item.get("display_name"),
                "ingress_port": item.get("ingress_port"),
                "frontend_upstream": item.get("frontend_base_url"),
                "backend_upstream": item.get("backend_base_url"),
            }
        )
        if normalized_item:
            normalized.append(normalized_item)
    return _normalize_port_sites(normalized)


def _runtime_host_sites_from_env(value: Any) -> list[dict[str, Any]]:
    rows = _coerce_mapping_list(value)
    normalized: list[dict[str, Any]] = []
    for item in rows:
        normalized_item = _normalize_host_site(
            {
                "site_key": item.get("site_key"),
                "display_name": item.get("display_name"),
                "hosts": item.get("hosts"),
                "frontend_upstream": item.get("frontend_base_url"),
                "backend_upstream": item.get("backend_base_url"),
            }
        )
        if normalized_item:
            normalized.append(normalized_item)
    return _normalize_host_sites(normalized)


def _with_derived(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    real = normalized["real"]
    frontend_url = _build_upstream_url(real["frontend_ip"], real["frontend_port"])
    backend_url = _build_upstream_url(real["backend_ip"], real["backend_port"])

    access_examples = [
        {
            "label": real["default_site_name"],
            "mode": "default_port",
            "ingress": int(real["gateway_port"]),
            "url": f"http://<IDS-IP>:{int(real['gateway_port'])}",
            "target": frontend_url,
        }
    ]

    for item in real["extra_port_sites"]:
        access_examples.append(
            {
                "label": item["display_name"],
                "mode": "port_map",
                "ingress": int(item["ingress_port"]),
                "url": f"http://<IDS-IP>:{int(item['ingress_port'])}",
                "target": item["frontend_upstream"],
            }
        )

    for item in real["host_sites"]:
        access_examples.append(
            {
                "label": item["display_name"],
                "mode": "host_map",
                "ingress": int(real["gateway_port"]),
                "url": ",".join(item["hosts"]),
                "target": item["frontend_upstream"],
            }
        )

    return {
        **normalized,
        "derived": {
            "frontend_upstream_url": frontend_url,
            "backend_upstream_url": backend_url,
            "gateway_port": int(real["gateway_port"]),
            "restart_required": True,
            "effective_scope": "default_upstream_port_map_and_site_map",
            "effective_hint": "运行期参数会回写 IDS 网关入口、默认回源地址、多站点入口映射和域名映射；默认回源与域名映射保存后重启 IDS Gateway 生效，如修改入口端口或新增附加端口且当前采用 Docker 部署，请重新应用 Compose 以同步宿主机端口映射。",
            "env_path": str(_ENV_PATH),
            "state_path": str(_COMMUNICATION_SETTINGS_PATH),
            "port_mapping_count": len(real["extra_port_sites"]),
            "host_mapping_count": len(real["host_sites"]),
            "access_examples": access_examples,
        },
    }


def _load_runtime_mapping_json(raw: str | None) -> list[dict[str, Any]] | None:
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return []
    try:
        return _coerce_mapping_list(json.loads(value))
    except Exception:
        return None


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

    stored_port_sites = _normalize_port_sites(merged["real"].get("extra_port_sites"))
    stored_host_sites = _normalize_host_sites(merged["real"].get("host_sites"))

    env_port_map = _load_runtime_mapping_json(env_values.get("IDS_GATEWAY_PORT_MAP"))
    env_site_map = _load_runtime_mapping_json(env_values.get("IDS_GATEWAY_SITE_MAP"))
    runtime_port_map = env_port_map if env_port_map is not None else settings.IDS_GATEWAY_PORT_MAP
    runtime_site_map = env_site_map if env_site_map is not None else settings.IDS_GATEWAY_SITE_MAP

    merged["real"]["extra_port_sites"] = _runtime_port_sites_from_env(runtime_port_map) or stored_port_sites
    merged["real"]["host_sites"] = _runtime_host_sites_from_env(runtime_site_map) or stored_host_sites

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

    frontend_url = _build_upstream_url(merged["real"]["frontend_ip"], merged["real"]["frontend_port"])
    backend_url = _build_upstream_url(merged["real"]["backend_ip"], merged["real"]["backend_port"])
    port_map = _port_map_from_runtime(merged["real"]["extra_port_sites"])
    site_map = _site_map_from_runtime(merged["real"]["host_sites"])

    _write_json_file(_COMMUNICATION_SETTINGS_PATH, merged)
    _write_env_values(
        {
            "IDS_GATEWAY_DEFAULT_PORT": str(merged["real"]["gateway_port"]),
            "IDS_GATEWAY_FRONTEND_BASE_URL": frontend_url,
            "IDS_GATEWAY_BACKEND_BASE_URL": backend_url,
            "IDS_GATEWAY_PORT_MAP": json.dumps(port_map, ensure_ascii=False, separators=(",", ":")),
            "IDS_GATEWAY_SITE_MAP": json.dumps(site_map, ensure_ascii=False, separators=(",", ":")),
        }
    )

    settings.IDS_GATEWAY_DEFAULT_PORT = int(merged["real"]["gateway_port"])
    settings.IDS_GATEWAY_FRONTEND_BASE_URL = frontend_url
    settings.IDS_GATEWAY_BACKEND_BASE_URL = backend_url
    settings.IDS_GATEWAY_PORT_MAP = [GatewayPortMapping.model_validate(item) for item in port_map]
    settings.IDS_GATEWAY_SITE_MAP = [GatewaySiteMapping.model_validate(item) for item in site_map]

    return _with_derived(merged)
