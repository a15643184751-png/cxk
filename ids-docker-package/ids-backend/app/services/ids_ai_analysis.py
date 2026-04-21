"""IDS post-hit LLM analysis grounded in the captured rule chain and request packet."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone

from ..config import settings
from ..database import SessionLocal
from ..models.ids_event import IDSEvent
from ..utils.llm_client import chat

logger = logging.getLogger("ids")

_ATTACK_LABELS = {
    "sql_injection": "SQL 注入",
    "xss": "跨站脚本 XSS",
    "xxe": "XXE 外部实体注入",
    "xml_external_entity": "XXE 外部实体注入",
    "path_traversal": "路径遍历",
    "cmd_injection": "命令注入",
    "scanner": "扫描器 / 探测",
    "malformed": "畸形请求",
    "jndi_injection": "JNDI / Log4Shell 类注入",
    "prototype_pollution": "原型链污染",
    "malware": "恶意载荷 / WebShell",
}


def _attack_label(attack_type: str) -> str:
    return _ATTACK_LABELS.get(attack_type, attack_type or "未知")


def is_llm_available() -> bool:
    if str(os.environ.get("IDS_FORCE_STATIC_MODE", "")).strip() == "1":
        return False
    if settings.LLM_PROVIDER == "ollama":
        return bool(settings.LLM_BASE_URL and settings.LLM_BASE_URL.strip())
    if settings.LLM_PROVIDER in ("openai", "deepseek", "kimi"):
        return bool(settings.LLM_API_KEY and str(settings.LLM_API_KEY).strip())
    return bool(settings.LLM_BASE_URL and str(settings.LLM_BASE_URL).strip())


def _extract_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _parse_risk_level(text: str) -> tuple[str, str, int]:
    obj = _extract_json(text)
    if obj:
        risk = str(obj.get("risk_level", "unknown")).lower()
        if risk not in ("high", "medium", "low", "unknown"):
            risk = "unknown"
        confidence = max(0, min(100, int(obj.get("confidence", 0) or 0)))
        summary = str(obj.get("summary") or "").strip()
        impact = str(obj.get("impact") or "").strip()
        evidence = [str(item).strip() for item in (obj.get("evidence") or []) if str(item).strip()][:5]
        actions = [str(item).strip() for item in (obj.get("actions") or []) if str(item).strip()][:5]
        body = (
            f"【研判摘要】{summary}\n"
            f"【影响评估】{impact}\n"
            f"【关键证据】{'; '.join(evidence)}\n"
            f"【处置建议】{'; '.join(actions)}"
        ).strip()
        return risk, body, confidence

    raw = (text or "").strip()
    if not raw:
        return "", "", 0
    first, _, rest = raw.partition("\n")
    match = re.match(r"^\s*RISK:\s*(high|medium|low|unknown)\s*$", first.strip(), re.I)
    if match:
        return match.group(1).lower(), (rest.strip() or raw), 0
    return "unknown", raw, 0


def _extract_event_hits(evt: IDSEvent) -> list[dict[str, str]]:
    raw = (evt.detect_detail or "").strip()
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []

    hits: list[dict[str, str]] = []
    for item in payload[:8]:
        if not isinstance(item, dict):
            continue
        hits.append(
            {
                "attack_type": str(item.get("attack_type") or "")[:64],
                "signature_matched": str(item.get("signature_matched") or item.get("pattern") or "")[:160],
                "pattern": str(item.get("pattern") or "")[:120],
                "source_rule_id": str(item.get("source_rule_id") or "")[:128],
                "source_rule_name": str(item.get("source_rule_name") or "")[:128],
                "source_version": str(item.get("source_version") or "")[:64],
                "source_classification": str(item.get("source_classification") or "")[:32],
                "detector_name": str(item.get("detector_name") or "")[:64],
            }
        )
    return hits


def _build_packet_preview(evt: IDSEvent) -> str:
    request_target = (evt.path or "").strip() or "/"
    query = (evt.query_snippet or "").strip()
    if query:
        request_target = f"{request_target}?{query[:240]}"

    lines = [
        f"{(evt.method or 'GET').upper()} {request_target[:420]} HTTP/1.1",
        "Host: blocked-by-ids.local",
    ]
    if (evt.user_agent or "").strip():
        lines.append(f"User-Agent: {(evt.user_agent or '')[:240]}")

    headers = (evt.headers_snippet or "").strip()
    if headers:
        lines.append(f"Captured-Headers: {headers[:480]}")

    body = (evt.body_snippet or "").strip()
    if body:
        lines.extend(["", body[:800]])
    return "\n".join(lines)


def build_analysis_prompt(evt: IDSEvent) -> str:
    label = _attack_label(evt.attack_type or "")
    hits = _extract_event_hits(evt)
    hit_lines = [
        (
            f"- rule_id={hit['source_rule_id'] or '-'}; "
            f"rule_name={hit['source_rule_name'] or '-'}; "
            f"signature={hit['signature_matched'] or '-'}; "
            f"source={hit['detector_name'] or '-'}; "
            f"class={hit['source_classification'] or '-'}; "
            f"version={hit['source_version'] or '-'}"
        )
        for hit in hits[:6]
    ]
    packet_preview = _build_packet_preview(evt)
    return f"""你是 Web 应用防火墙 IDS 分析助手。以下请求已经被静态规则引擎判定为可疑并返回 HTTP 403。
请严格输出 JSON，不要输出额外解释，格式如下：
{{
  "risk_level": "high|medium|low|unknown",
  "confidence": 0,
  "summary": "1-3句中文摘要",
  "impact": "对业务或数据的影响",
  "evidence": ["证据1", "证据2"],
  "actions": ["建议动作1", "建议动作2"]
}}

已知字段：
- 攻击类型（规则）: {label} ({evt.attack_type})
- 匹配特征摘要: {(evt.signature_matched or '')[:200]}
- 命中规则链：
{chr(10).join(hit_lines) if hit_lines else "- no structured hit chain captured"}
- 方法: {evt.method} 路径: {(evt.path or '')[:300]}
- Query 片段: {(evt.query_snippet or '')[:400]}
- Body 片段: {(evt.body_snippet or '')[:400]}
- Headers 片段: {(evt.headers_snippet or '')[:400]}
- User-Agent: {(evt.user_agent or '')[:300]}
- 客户端 IP: {evt.client_ip}
- 规则源分类: {(evt.source_classification or '')[:32]}
- 检测器: {(evt.detector_name or '')[:64]}
- 规则 ID: {(evt.source_rule_id or '')[:128]}
- 规则名: {(evt.source_rule_name or '')[:128]}
- 规则版本: {(evt.source_version or '')[:64]}
- 风险分数（规则引擎）: {getattr(evt, 'risk_score', 0)}/100
- 规则置信度: {getattr(evt, 'confidence', 0)}/100

请求包预览：
{packet_preview[:1800]}
"""


def run_ai_analysis_sync(event_id: int) -> None:
    if not settings.IDS_AI_ANALYSIS or not is_llm_available():
        return

    db = SessionLocal()
    try:
        evt = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
        if not evt:
            return
        prompt = build_analysis_prompt(evt)
        messages = [
            {
                "role": "system",
                "content": "你只能输出 JSON，不要输出解释文字；不要编造不存在的字段；不确定时 risk_level=unknown。",
            },
            {"role": "user", "content": prompt},
        ]
        out = chat(messages)
        if not out:
            logger.info("IDS AI: empty response for event_id=%s", event_id)
            return

        risk, body, ai_conf = _parse_risk_level(out)
        evt.ai_risk_level = risk or "unknown"
        evt.ai_analysis = (body or out)[:8000]
        evt.ai_confidence = ai_conf
        evt.ai_analyzed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.warning("IDS AI analysis failed event_id=%s: %s", event_id, exc)
        db.rollback()
    finally:
        db.close()


def schedule_ai_analysis(event_id: int) -> None:
    if not settings.IDS_AI_ANALYSIS or not is_llm_available():
        return

    def _job() -> None:
        try:
            run_ai_analysis_sync(event_id)
        except Exception as exc:
            logger.warning("IDS AI background task failed: %s", exc)

    thread = threading.Thread(target=_job, name=f"ids-ai-{event_id}", daemon=True)
    thread.start()
