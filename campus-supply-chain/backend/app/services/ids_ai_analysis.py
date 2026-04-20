"""IDS 命中后的 LLM 异步研判（与规则引擎互补，不替代拦截）。"""
from __future__ import annotations

import logging
import re
import json
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
    "path_traversal": "路径遍历",
    "cmd_injection": "命令注入",
    "scanner": "扫描器/探测",
    "malformed": "畸形请求",
    "jndi_injection": "JNDI/Log4j 类注入",
    "prototype_pollution": "原型链污染",
}


def _attack_label(t: str) -> str:
    return _ATTACK_LABELS.get(t, t or "未知")


def is_llm_available() -> bool:
    if settings.LLM_PROVIDER == "ollama":
        return bool(settings.LLM_BASE_URL and settings.LLM_BASE_URL.strip())
    if settings.LLM_PROVIDER in ("openai", "deepseek"):
        return bool(settings.LLM_API_KEY and str(settings.LLM_API_KEY).strip())
    return bool(settings.LLM_BASE_URL and str(settings.LLM_BASE_URL).strip())


def _extract_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _parse_risk_level(text: str) -> tuple[str, str, int]:
    """解析 JSON 输出，不满足时回退到文本。"""
    obj = _extract_json(text)
    if obj:
        risk = str(obj.get("risk_level", "unknown")).lower()
        if risk not in ("high", "medium", "low", "unknown"):
            risk = "unknown"
        confidence = int(obj.get("confidence", 0) or 0)
        confidence = max(0, min(100, confidence))
        summary = obj.get("summary", "")
        evidence = obj.get("evidence", [])
        actions = obj.get("actions", [])
        impact = obj.get("impact", "")
        body = (
            f"【研判摘要】{summary}\n"
            f"【影响评估】{impact}\n"
            f"【关键证据】{'; '.join([str(x) for x in evidence][:5])}\n"
            f"【处置建议】{'; '.join([str(x) for x in actions][:5])}"
        ).strip()
        return risk, body, confidence
    raw = (text or "").strip()
    if not raw:
        return "", "", 0
    first, _, rest = raw.partition("\n")
    m = re.match(r"^\s*RISK:\s*(high|medium|low|unknown)\s*$", first.strip(), re.I)
    if m:
        return m.group(1).lower(), (rest.strip() or raw), 0
    return "unknown", raw, 0


def build_analysis_prompt(evt: IDSEvent) -> str:
    label = _attack_label(evt.attack_type or "")
    return f"""你是 Web 应用防火墙/IDS 分析助手。以下请求已被**规则引擎**判定为可疑并已拦截（HTTP 403）。
请用中文输出严格 JSON，不要输出多余文字，格式如下：
{{
  "risk_level": "high|medium|low|unknown",
  "confidence": 0-100,
  "summary": "1-3句研判摘要",
  "impact": "对业务或数据影响",
  "evidence": ["证据1","证据2"],
  "actions": ["建议动作1","建议动作2"]
}}

已知字段：
- 攻击类型（规则）: {label} ({evt.attack_type})
- 匹配特征摘要: {(evt.signature_matched or '')[:200]}
- 方法: {evt.method} 路径: {(evt.path or '')[:300]}
- Query 片段: {(evt.query_snippet or '')[:400]}
- Body 片段: {(evt.body_snippet or '')[:400]}
- User-Agent: {(evt.user_agent or '')[:300]}
- 客户端 IP: {evt.client_ip}
- 风险分值（规则引擎）: {getattr(evt, 'risk_score', 0)}/100
- 规则置信度: {getattr(evt, 'confidence', 0)}/100
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
                "content": "你只输出 JSON，不要输出解释文字，不要编造不存在的字段；不确定时 risk_level=unknown。",
            },
            {"role": "user", "content": prompt},
        ]
        out = chat(messages)
        if not out:
            logger.info("IDS AI: LLM 无返回 event_id=%s", event_id)
            return
        risk, body, ai_conf = _parse_risk_level(out)
        evt.ai_risk_level = risk or "unknown"
        evt.ai_analysis = (body or out)[:8000]
        evt.ai_confidence = ai_conf
        evt.ai_analyzed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        logger.warning("IDS AI 研判失败 event_id=%s: %s", event_id, e)
        db.rollback()
    finally:
        db.close()


def schedule_ai_analysis(event_id: int) -> None:
    if not settings.IDS_AI_ANALYSIS or not is_llm_available():
        return

    def _job():
        try:
            run_ai_analysis_sync(event_id)
        except Exception as e:
            logger.warning("IDS AI 后台任务异常: %s", e)

    t = threading.Thread(target=_job, name=f"ids-ai-{event_id}", daemon=True)
    t.start()
