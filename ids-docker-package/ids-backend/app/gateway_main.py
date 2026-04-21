from __future__ import annotations

import fnmatch
import html
import time
from typing import Iterable
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.cors import CORSMiddleware

from .config import GatewayPortMapping, GatewaySiteMapping, PRIVATE_LAN_CORS_REGEX, settings
from .database import SessionLocal
from .schema_sync import ensure_schema
from .database import Base, engine
from .services.ids_blocklist import is_ip_blocked
from .services.ids_engine import scan_frontend_route_probe, scan_request_detailed
from .services.ids_http_capture import (
    build_raw_request,
    build_raw_response,
    format_header_lines,
    save_http_session,
)
from .services.ids_request_probe import persist_request_detection

Base.metadata.create_all(bind=engine)
ensure_schema(engine)

app = FastAPI(title="IDS HTTP Gateway", version="1.0.0")

cors_options: dict = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ALLOW_PRIVATE_NETWORKS:
    cors_options["allow_origin_regex"] = PRIVATE_LAN_CORS_REGEX
app.add_middleware(CORSMiddleware, **cors_options)

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _client_ip(request: Request) -> str:
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "0.0.0.0"


def _is_backend_route(path: str) -> bool:
    return (
        path.startswith("/api")
        or path.startswith("/uploads")
        or path.startswith("/docs")
        or path.startswith("/openapi.json")
    )


def _normalize_host(value: str) -> str:
    host = str(value or "").split(",", 1)[0].strip()
    if not host:
        return ""
    if host.startswith("["):
        closing_index = host.find("]")
        return host[1:closing_index].strip().lower().rstrip(".") if closing_index > 0 else host.strip().lower().rstrip(".")
    if host.count(":") == 1 and host.rsplit(":", 1)[1].isdigit():
        host = host.rsplit(":", 1)[0]
    return host.strip().lower().rstrip(".")


def _request_port(request: Request) -> int:
    if request.url.port:
        return int(request.url.port)

    host_header = str(request.headers.get("host") or "").strip()
    if host_header.count(":") == 1 and host_header.rsplit(":", 1)[1].isdigit():
        return int(host_header.rsplit(":", 1)[1])

    return int(settings.IDS_GATEWAY_DEFAULT_PORT or 8188)


def _match_gateway_port(port: int) -> GatewayPortMapping | None:
    for item in settings.IDS_GATEWAY_PORT_MAP:
        if int(item.ingress_port or 0) == int(port or 0):
            return item
    return None


def _match_gateway_site(request_host: str) -> GatewaySiteMapping | None:
    normalized_host = _normalize_host(request_host)
    if not normalized_host:
        return None

    for site in settings.IDS_GATEWAY_SITE_MAP:
        for candidate in site.hosts:
            if not candidate:
                continue
            if "*" in candidate:
                if fnmatch.fnmatch(normalized_host, candidate):
                    return site
                continue
            if normalized_host == candidate:
                return site
    return None


def _target_base_for_path(
    path: str,
    request_host: str,
    request_port: int,
) -> tuple[str, str, GatewaySiteMapping | None, GatewayPortMapping | None]:
    matched_port = _match_gateway_port(request_port)
    if matched_port:
        if _is_backend_route(path):
            return matched_port.backend_base_url, "api", None, matched_port
        return matched_port.frontend_base_url, "frontend", None, matched_port

    matched_site = _match_gateway_site(request_host)
    if _is_backend_route(path):
        if matched_site and matched_site.backend_base_url:
            return matched_site.backend_base_url, "api", matched_site, None
        return settings.IDS_GATEWAY_BACKEND_BASE_URL, "api", matched_site, None
    if matched_site and matched_site.frontend_base_url:
        return matched_site.frontend_base_url, "frontend", matched_site, None
    return settings.IDS_GATEWAY_FRONTEND_BASE_URL, "frontend", matched_site, None


def _forward_headers(request: Request, client_ip: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lower = name.lower()
        if lower in _HOP_BY_HOP_HEADERS or lower == "host" or lower == "content-length":
            continue
        headers[name] = value
    headers["X-Forwarded-For"] = client_ip
    headers["X-Real-IP"] = client_ip
    headers["X-Forwarded-Proto"] = request.url.scheme
    if request.headers.get("host"):
        headers["X-Forwarded-Host"] = request.headers["host"]
    return headers


def _response_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for name, value in headers:
        if name.lower() in _HOP_BY_HOP_HEADERS or name.lower() == "content-length":
            continue
        clean[name] = value
    return clean


def _prefers_html(request: Request, path: str) -> bool:
    if _is_backend_route(path):
        return False
    accept = str(request.headers.get("accept") or "").lower()
    fetch_dest = str(request.headers.get("sec-fetch-dest") or "").lower()
    return "text/html" in accept or fetch_dest == "document" or accept in {"", "*/*"}


def _render_blocked_html(*, client_ip: str, path: str, title: str, summary: str, badge: str, hint: str) -> str:
    safe_client_ip = html.escape(client_ip or "-")
    safe_path = html.escape(path or "/")
    safe_title = html.escape(title)
    safe_summary = html.escape(summary)
    safe_badge = html.escape(badge)
    safe_hint = html.escape(hint)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>403 Forbidden</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #050816;
      --panel: rgba(7, 13, 26, 0.9);
      --line: rgba(148, 163, 184, 0.16);
      --text: #e5eefb;
      --muted: rgba(191, 219, 254, 0.74);
      --danger: #f87171;
      --accent: #67e8f9;
      --amber: #fbbf24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      color: var(--text);
      background:
        radial-gradient(circle at 15% 20%, rgba(239, 68, 68, 0.18), transparent 24%),
        radial-gradient(circle at 85% 18%, rgba(56, 189, 248, 0.16), transparent 22%),
        linear-gradient(160deg, #020617, #09111f 48%, #050816);
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    }}
    .panel {{
      width: min(920px, 100%);
      border: 1px solid var(--line);
      border-radius: 28px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: 0 30px 90px rgba(2, 6, 23, 0.45);
    }}
    .hero {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid var(--line);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(248, 113, 113, 0.12);
      color: #fecaca;
      font-size: 12px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 18px 0 10px;
      font-size: clamp(32px, 5vw, 64px);
      line-height: 1;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.75;
      font-size: 15px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      padding: 22px 32px 32px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      background: rgba(15, 23, 42, 0.76);
    }}
    .label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .value {{
      display: block;
      margin-top: 10px;
      font-size: 20px;
      color: var(--text);
      word-break: break-all;
    }}
    .signal {{
      color: var(--danger);
      font-weight: 700;
    }}
    .hint {{
      color: var(--amber);
      font-size: 13px;
    }}
    @media (max-width: 720px) {{
      .grid {{
        grid-template-columns: 1fr;
        padding: 18px;
      }}
      .hero {{
        padding: 22px 18px 16px;
      }}
    }}
  </style>
</head>
<body>
  <section class="panel">
    <div class="hero">
      <span class="badge">{safe_badge}</span>
      <h1>403</h1>
      <p class="signal">{safe_title}</p>
      <p>{safe_summary}</p>
    </div>
    <div class="grid">
      <article class="card">
        <span class="label">源地址</span>
        <strong class="value">{safe_client_ip}</strong>
      </article>
      <article class="card">
        <span class="label">访问路径</span>
        <strong class="value">{safe_path}</strong>
      </article>
      <article class="card">
        <span class="label">处置结果</span>
        <strong class="value">请求已被安全网关拒绝</strong>
      </article>
      <article class="card">
        <span class="label">说明</span>
        <strong class="value hint">{safe_hint}</strong>
      </article>
    </div>
  </section>
</body>
</html>"""


def _build_block_response(request: Request, path: str, payload: dict, *, title: str, summary: str, badge: str, hint: str):
    if _prefers_html(request, path):
        return HTMLResponse(
            status_code=403,
            content=_render_blocked_html(
                client_ip=str(payload.get("client_ip") or "-"),
                path=path,
                title=title,
                summary=summary,
                badge=badge,
                hint=hint,
            ),
        )
    return JSONResponse(status_code=403, content=payload)


@app.get("/gateway/health")
def gateway_health() -> dict:
    return {
        "status": "ok",
        "service": "ids_http_gateway",
        "default_port": int(settings.IDS_GATEWAY_DEFAULT_PORT or 8188),
        "frontend_upstream": settings.IDS_GATEWAY_FRONTEND_BASE_URL,
        "backend_upstream": settings.IDS_GATEWAY_BACKEND_BASE_URL,
        "site_count": len(settings.IDS_GATEWAY_SITE_MAP),
        "port_mapping_count": len(settings.IDS_GATEWAY_PORT_MAP),
        "sites": [
            {
                "site_key": site.site_key,
                "display_name": site.display_name,
                "hosts": site.hosts,
                "frontend_upstream": site.frontend_base_url,
                "backend_upstream": site.backend_base_url,
            }
            for site in settings.IDS_GATEWAY_SITE_MAP
        ],
        "ports": [
            {
                "site_key": item.site_key,
                "display_name": item.display_name,
                "ingress_port": int(item.ingress_port or 0),
                "frontend_upstream": item.frontend_base_url,
                "backend_upstream": item.backend_base_url,
            }
            for item in settings.IDS_GATEWAY_PORT_MAP
        ],
    }


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def gateway_proxy(full_path: str, request: Request):
    path = f"/{full_path}".replace("//", "/")
    client_ip = _client_ip(request)
    request_body_bytes = await request.body()
    request_host = request.headers.get("host", "")
    request_port = _request_port(request)
    upstream_base, route_kind, matched_site, matched_port = _target_base_for_path(path, request_host, request_port)
    matched_site_key = (matched_site.site_key or "").strip() if matched_site else ""
    matched_port_site_key = (matched_port.site_key or "").strip() if matched_port else ""
    if matched_port_site_key:
        gateway_note_suffix = f";site={matched_port_site_key};port={request_port}"
    elif matched_site_key:
        gateway_note_suffix = f";site={matched_site_key}"
    else:
        gateway_note_suffix = ""
    if is_ip_blocked(client_ip):
        payload = {
            "detail": "Request blocked by IDS IP policy",
            "code": "IDS_IP_BLOCKED",
            "client_ip": client_ip,
            "path": path,
            "host": request_host,
            "site_key": matched_port_site_key or matched_site_key,
            "ingress_port": request_port,
        }
        raw_request, request_body = build_raw_request(
            request.method,
            path + (f"?{request.url.query}" if request.url.query else ""),
            list(request.headers.items()),
            request_body_bytes,
        )
        blocked_response = _build_block_response(
            request,
            path,
            payload,
            title="源地址已被标记为封禁对象",
            summary="该请求在进入业务系统之前已被安全网关拦截。",
            badge="IDS BLOCK POLICY",
            hint="该源地址已命中 IP 封禁策略，如需继续访问请联系管理员复核。",
        )
        raw_response, response_body = build_raw_response(
            403,
            [("content-type", blocked_response.media_type or "text/html; charset=utf-8")],
            blocked_response.body,
        )
        db = SessionLocal()
        try:
            save_http_session(
                db,
                client_ip=client_ip,
                scheme=request.url.scheme,
                host=request.headers.get("host", ""),
                method=request.method,
                path=path,
                query_string=request.url.query,
                route_kind="api" if _is_backend_route(path) else "frontend",
                upstream_base="",
                upstream_url="",
                user_agent=request.headers.get("user-agent", ""),
                request_headers=format_header_lines(request.headers.items()),
                request_body=request_body,
                raw_request=raw_request,
                request_size=len(request_body_bytes),
                response_status=403,
                response_headers=f"content-type: {blocked_response.media_type or 'text/html; charset=utf-8'}",
                response_body=response_body,
                raw_response=raw_response,
                response_size=len(blocked_response.body),
                content_type=blocked_response.media_type or "text/html; charset=utf-8",
                duration_ms=0,
                blocked=True,
                attack_type="blocked_ip",
                response_note=f"blocked_by_gateway_ip_policy{gateway_note_suffix}",
            )
        finally:
            db.close()
        return blocked_response

    raw_request, request_body = build_raw_request(
        request.method,
        path + (f"?{request.url.query}" if request.url.query else ""),
        list(request.headers.items()),
        request_body_bytes,
    )
    detection = scan_request_detailed(
        request.method,
        path,
        request.url.query,
        request_body,
        dict(request.headers),
        request.headers.get("user-agent", ""),
    )
    if route_kind == "frontend":
        probe_detection = scan_frontend_route_probe(
            path,
            request.url.query,
            request.headers.get("user-agent", ""),
        )
        if probe_detection.get("matched") and int(probe_detection.get("risk_score") or 0) >= int(detection.get("risk_score") or 0):
            detection = probe_detection

    incident_id: int | None = None
    should_block = bool(detection.get("matched") and int(detection.get("risk_score") or 0) >= int(settings.IDS_BLOCK_THRESHOLD))
    if should_block:
        db = SessionLocal()
        try:
            outcome = persist_request_detection(
                db,
                client_ip=client_ip,
                method=request.method,
                path=path,
                query=request.url.query,
                body_str=request_body,
                headers=dict(request.headers),
                user_agent=request.headers.get("user-agent", ""),
                detection=detection,
            )
            incident_id = int(outcome.get("incident_id") or 0) or None
        finally:
            db.close()

        payload = {
            "detail": "Request blocked by IDS gateway security policy",
            "code": "IDS_GATEWAY_BLOCKED",
            "attack_type": str(detection.get("attack_type") or ""),
            "risk_score": int(detection.get("risk_score") or 0),
            "confidence": int(detection.get("confidence") or 0),
            "incident_id": incident_id,
            "path": path,
            "client_ip": client_ip,
            "host": request_host,
            "site_key": matched_port_site_key or matched_site_key,
            "ingress_port": request_port,
        }
        blocked_response = _build_block_response(
            request,
            path,
            payload,
            title="检测到高风险访问行为",
            summary="该请求已命中安全网关检测规则，并在转发到业务系统之前被阻断。",
            badge="IDS ACTIVE DEFENSE",
            hint="当前请求特征已命中高风险检测规则，系统已自动完成拦截与留痕。",
        )
        raw_response, response_body = build_raw_response(
            403,
            [("content-type", blocked_response.media_type or "text/html; charset=utf-8")],
            blocked_response.body,
        )
        db = SessionLocal()
        try:
            save_http_session(
                db,
                client_ip=client_ip,
                scheme=request.url.scheme,
                host=request.headers.get("host", ""),
                method=request.method,
                path=path,
                query_string=request.url.query,
                route_kind=route_kind,
                upstream_base=upstream_base,
                upstream_url=urljoin(f"{upstream_base}/", path.lstrip("/")),
                user_agent=request.headers.get("user-agent", ""),
                request_headers=format_header_lines(request.headers.items()),
                request_body=request_body,
                raw_request=raw_request,
                request_size=len(request_body_bytes),
                response_status=403,
                response_headers=f"content-type: {blocked_response.media_type or 'text/html; charset=utf-8'}",
                response_body=response_body,
                raw_response=raw_response,
                response_size=len(blocked_response.body),
                content_type=blocked_response.media_type or "text/html; charset=utf-8",
                duration_ms=0,
                blocked=True,
                attack_type=str(detection.get("attack_type") or ""),
                risk_score=int(detection.get("risk_score") or 0),
                confidence=int(detection.get("confidence") or 0),
                incident_id=incident_id,
                response_note=f"blocked_by_ids_gateway{gateway_note_suffix}",
            )
        finally:
            db.close()
        return blocked_response

    upstream_url = urljoin(f"{upstream_base}/", path.lstrip("/"))
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    started_at = time.perf_counter()
    async with httpx.AsyncClient(timeout=httpx.Timeout(float(settings.IDS_GATEWAY_TIMEOUT_SECONDS or 30.0)), trust_env=False) as client:
        upstream_response = await client.request(
            request.method,
            upstream_url,
            headers=_forward_headers(request, client_ip),
            content=request_body_bytes if request_body_bytes else None,
        )
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    response_body_bytes = upstream_response.content
    raw_response, response_body = build_raw_response(upstream_response.status_code, list(upstream_response.headers.items()), response_body_bytes)

    db = SessionLocal()
    try:
        save_http_session(
            db,
            client_ip=client_ip,
            scheme=request.url.scheme,
            host=request.headers.get("host", ""),
            method=request.method,
            path=path,
            query_string=request.url.query,
            route_kind=route_kind,
            upstream_base=upstream_base,
            upstream_url=upstream_url,
            user_agent=request.headers.get("user-agent", ""),
            request_headers=format_header_lines(request.headers.items()),
            request_body=request_body,
            raw_request=raw_request,
            request_size=len(request_body_bytes),
            response_status=upstream_response.status_code,
            response_headers=format_header_lines(upstream_response.headers.items()),
            response_body=response_body,
            raw_response=raw_response,
            response_size=len(response_body_bytes),
            content_type=upstream_response.headers.get("content-type", ""),
            duration_ms=duration_ms,
            blocked=False,
            response_note=f"proxied_by_ids_gateway{gateway_note_suffix}",
        )
    finally:
        db.close()

    return Response(
        content=response_body_bytes,
        status_code=upstream_response.status_code,
        headers=_response_headers(upstream_response.headers.items()),
    )
