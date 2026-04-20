"""Public upload APIs with standalone IDS forwarding."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..models.user import User
from ..services.ids_standalone_bridge import standalone_ids_enabled, submit_upload_to_standalone
from .deps import require_roles

router = APIRouter(prefix="/upload", tags=["upload"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_admin = require_roles("system_admin")

HIGH_RISK_EXT = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".scr", ".com", ".dll", ".msi"}
MEDIUM_RISK_EXT = {".php", ".jsp", ".asp", ".aspx", ".zip", ".jar", ".vbs", ".js", ".html", ".htm"}


def _risk_for_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in HIGH_RISK_EXT:
        return "high"
    if suffix in MEDIUM_RISK_EXT:
        return "medium"
    return "low"


def _client_public_base(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if forwarded_host:
        host = forwarded_host.split(",")[0].strip()
        scheme = forwarded_proto or "http"
        return f"{scheme}://{host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _request_ip(request: Request) -> str:
    for header_name in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = request.headers.get(header_name)
        if value:
            return value.split(",")[0].strip()[:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return "0.0.0.0"


def _safe_upload_path(name: str) -> Path | None:
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    path = (UPLOAD_DIR / Path(name).name).resolve()
    try:
        path.relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        return None
    return path


@router.get("/quarantine")
def list_quarantine(request: Request, _: User = Depends(_admin)):
    base = str(request.base_url).rstrip("/")
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    items: list[dict] = []
    total_bytes = 0
    by_ext: dict[str, int] = defaultdict(int)
    daily: dict[str, int] = defaultdict(int)
    high_count = 0
    medium_count = 0

    if UPLOAD_DIR.exists():
        for path in sorted(UPLOAD_DIR.iterdir(), key=lambda entry: entry.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            stat = path.stat()
            total_bytes += stat.st_size
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            iso_time = modified_at.isoformat()
            extension = Path(path.name).suffix.lower() or "(none)"
            by_ext[extension] += 1
            daily[modified_at.strftime("%Y-%m-%d")] += 1
            risk = _risk_for_name(path.name)
            if risk == "high":
                high_count += 1
            elif risk == "medium":
                medium_count += 1
            items.append(
                {
                    "saved_as": path.name,
                    "size": stat.st_size,
                    "modified_at": iso_time,
                    "url": f"{base}/uploads/{path.name}" if base else f"/uploads/{path.name}",
                    "risk_level": risk,
                    "extension": extension,
                }
            )

    labels: list[str] = []
    counts: list[int] = []
    for offset in range(13, -1, -1):
        label_date = (today_start - timedelta(days=offset)).strftime("%Y-%m-%d")
        labels.append(label_date[5:])
        counts.append(daily.get(label_date, 0))

    today_count = sum(1 for item in items if item["modified_at"][:10] == today_start.strftime("%Y-%m-%d"))
    week_count = sum(
        1
        for item in items
        if datetime.fromisoformat(item["modified_at"].replace("Z", "+00:00")) >= week_start
    )

    top_ext = sorted(by_ext.items(), key=lambda item: -item[1])[:6]
    insights: list[str] = []
    if not items:
        insights.append("当前本地上传目录为空，如已启用集中送检链路可忽略。")
    else:
        insights.append(f"本地目录共保留 {len(items)} 个对象，占用 {total_bytes / 1024 / 1024:.2f} MB。")
        if high_count:
            insights.append(f"检测到 {high_count} 个高风险扩展名对象，建议优先复核。")
        if medium_count:
            insights.append(f"另有 {medium_count} 个中风险对象，建议放到隔离环境分析。")

    analysis = {
        "total_bytes": total_bytes,
        "today_count": today_count,
        "week_count": week_count,
        "high_risk_count": high_count,
        "medium_risk_count": medium_count,
        "by_extension": [{"ext": ext, "count": count} for ext, count in top_ext],
        "daily_labels": labels,
        "daily_counts": counts,
        "insights": insights,
        "generated_at": now.isoformat(),
    }

    return {"items": items, "count": len(items), "analysis": analysis}


@router.delete("/quarantine/{filename:path}")
def delete_quarantine_file(filename: str, _: User = Depends(_admin)):
    path = _safe_upload_path(filename)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    path.unlink()
    return {"ok": True}


@router.post("")
async def public_upload(request: Request, file: UploadFile = File(...)):
    safe_name = Path(file.filename or "unnamed").name
    content = await file.read()
    standalone_enabled = standalone_ids_enabled()

    forwarded = await submit_upload_to_standalone(
        file_name=safe_name,
        content=content,
        client_ip=_request_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    if forwarded.get("ok"):
        payload = forwarded.get("data") or {}
        if isinstance(payload, dict):
            payload.setdefault("filename", safe_name)
            payload.setdefault("size", len(content))
            payload.setdefault("via_ids_standalone", True)
        return payload

    if standalone_enabled:
        reason = str(forwarded.get("reason") or "独立 IDS 未响应")[:300]
        raise HTTPException(
            status_code=503,
            detail=f"独立 IDS 上传桥接失败：{reason}",
        )

    unique = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    destination = UPLOAD_DIR / unique
    destination.write_bytes(content)
    base = _client_public_base(request)
    response = {
        "ok": True,
        "filename": safe_name,
        "saved_as": unique,
        "size": len(content),
        "url": f"{base}/uploads/{unique}",
        "via_ids_standalone": False,
        "security_alert": {
            "style": "simulated_403_malware",
            "http_status_hint": 403,
            "title": "403 Forbidden 木马 / WebShell 安全告警",
            "message": "安全分析服务当前未接通，文件已按本地隔离策略落盘并标记为高风险样本。",
            "detail": f"原始文件名：{safe_name}；落盘名：{unique}；大小：{len(content)} 字节",
        },
    }
    if forwarded.get("reason"):
        response["ids_forward_error"] = str(forwarded.get("reason"))[:300]
    return response
