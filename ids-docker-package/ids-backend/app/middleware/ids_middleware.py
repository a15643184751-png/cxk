"""IDS middleware for request inspection, event persistence, and blocking."""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import settings
from ..database import SessionLocal
from ..services.ids_blocklist import is_ip_blocked
from ..services.ids_engine import _extract_text, is_whitelisted, scan_request_detailed
from ..services.ids_request_probe import persist_request_detection

logger = logging.getLogger("ids")


def _get_client_ip(request: Request) -> str:
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    if request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


class IDSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = _get_client_ip(request)
        path = request.url.path
        method = request.method
        if method != "OPTIONS" and is_ip_blocked(client_ip):
            logger.info("IDS application blocklist denied request from %s to %s", client_ip, path)
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Request blocked by IDS IP policy",
                    "code": "IDS_IP_BLOCKED",
                    "client_ip": client_ip,
                    "path": path,
                },
            )
        if method == "OPTIONS" or is_whitelisted(path):
            return await call_next(request)

        query = str(request.query_params)
        headers = dict(request.headers)
        user_agent = headers.get("user-agent", "")
        body_str = ""
        body_bytes = b""

        if method in ("POST", "PUT", "PATCH", "DELETE") and settings.IDS_MAX_BODY_BYTES > 0:
            try:
                body_bytes = await request.body()
                cap = min(len(body_bytes), max(1, settings.IDS_MAX_BODY_BYTES))
                body_str = _extract_text(body_bytes[:cap], settings.IDS_MAX_BODY_BYTES)
            except Exception as exc:
                logger.debug("IDS body read skip: %s", exc)
                body_bytes = b""
                body_str = ""

            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive)

        detection = scan_request_detailed(method, path, query, body_str, headers, user_agent)
        if not detection.get("matched"):
            return await call_next(request)

        db = SessionLocal()
        outcome: dict[str, object] = {
            "incident_id": None,
            "blocked": False,
            "should_block": bool(int(detection.get("risk_score") or 0) >= int(settings.IDS_BLOCK_THRESHOLD)),
            "attack_type": str(detection.get("attack_type") or ""),
            "risk_score": int(detection.get("risk_score") or 0),
            "confidence": int(detection.get("confidence") or 0),
        }
        try:
            outcome = persist_request_detection(
                db,
                client_ip=client_ip,
                method=method,
                path=path,
                query=query,
                body_str=body_str,
                headers=headers,
                user_agent=user_agent,
                detection=detection,
            )
        except Exception as exc:
            logger.warning("IDS event persistence failed: %s", exc)
        finally:
            db.close()

        if bool(outcome.get("should_block")):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Request blocked by IDS security policy",
                    "code": "IDS_BLOCKED",
                    "attack_type": str(outcome.get("attack_type") or ""),
                    "risk_score": int(outcome.get("risk_score") or 0),
                    "confidence": int(outcome.get("confidence") or 0),
                    "incident_id": outcome.get("incident_id"),
                },
            )
        return await call_next(request)
