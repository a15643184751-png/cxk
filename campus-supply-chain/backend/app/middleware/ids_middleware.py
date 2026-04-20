"""IDS 中间件：解析 HTTP 请求（含有限 Body）、评分检测、阻断/记录、留痕与 AI 研判。"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from ..config import settings
from ..database import SessionLocal
from ..models.ids_event import IDSEvent
from ..services.ids_engine import scan_request_detailed, block_ip_windows, is_whitelisted, _extract_text
from ..services.ids_ai_analysis import schedule_ai_analysis
from ..services.ids_standalone_bridge import ingest_runtime_detection

logger = logging.getLogger("ids")


def _get_client_ip(request: Request) -> str:
    for h in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        v = request.headers.get(h)
        if v:
            return v.split(",")[0].strip()
    if request.client:
        return request.client.host or "0.0.0.0"
    return "0.0.0.0"


class IDSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = _get_client_ip(request)
        path = request.url.path
        if is_whitelisted(path):
            return await call_next(request)

        method = request.method
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
            except Exception as e:
                logger.debug("IDS body read skip: %s", e)
                body_bytes = b""
                body_str = ""

            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request = Request(request.scope, receive)

        detection = scan_request_detailed(method, path, query, body_str, headers, user_agent)
        if not detection.get("matched"):
            return await call_next(request)

        attack_type = str(detection.get("attack_type") or "")
        signature_matched = str(detection.get("signature_matched") or "")
        risk_score = int(detection.get("risk_score") or 0)
        confidence = int(detection.get("confidence") or 0)
        hit_count = int(detection.get("hit_count") or 0)
        detect_detail = str(detection.get("detect_detail") or "")
        blocked = 0
        firewall_rule = ""
        should_block = risk_score >= int(settings.IDS_BLOCK_THRESHOLD)
        status = "investigating"
        action_taken = "record_only"

        if should_block and settings.IDS_FIREWALL_BLOCK:
            try:
                ok, msg = block_ip_windows(client_ip)
                if ok:
                    blocked = 1
                    firewall_rule = msg
                    logger.warning("IDS: 已封禁 %s 攻击来自 %s", attack_type, client_ip)
                    action_taken = "firewall_block"
                else:
                    action_taken = "block_failed_recorded"
            except Exception as e:
                logger.warning("IDS: 防火墙封禁失败 %s", e)
                action_taken = "block_failed_recorded"
        elif should_block:
            action_taken = "logical_block_only"

        db = SessionLocal()
        evt_id: int | None = None
        try:
            evt = IDSEvent(
                client_ip=client_ip,
                attack_type=attack_type,
                signature_matched=signature_matched[:128],
                method=method,
                path=path[:512],
                query_snippet=query[:500],
                body_snippet=(body_str or "")[:500],
                user_agent=user_agent[:512],
                headers_snippet=str(headers)[:1000],
                blocked=blocked,
                firewall_rule=firewall_rule[:256],
                status=status,
                action_taken=action_taken,
                risk_score=risk_score,
                confidence=confidence,
                hit_count=hit_count,
                detect_detail=detect_detail,
            )
            db.add(evt)
            db.commit()
            db.refresh(evt)
            evt_id = evt.id
        except Exception as e:
            logger.warning("IDS: 留痕写入失败 %s", e)
            db.rollback()
        finally:
            db.close()

        if evt_id is not None:
            schedule_ai_analysis(evt_id)

        await ingest_runtime_detection(
            client_ip=client_ip,
            method=method,
            path=path,
            query=query,
            body_snippet=body_str,
            user_agent=user_agent,
            headers_snippet=str(headers)[:1000],
            attack_type=attack_type,
            signature_matched=signature_matched,
            risk_score=risk_score,
            confidence=confidence,
            blocked=should_block,
            action_taken=action_taken,
            firewall_rule=firewall_rule,
        )

        if should_block:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "请求已被安全策略拦截",
                    "code": "IDS_BLOCKED",
                    "attack_type": attack_type,
                    "risk_score": risk_score,
                    "confidence": confidence,
                },
            )
        return await call_next(request)
