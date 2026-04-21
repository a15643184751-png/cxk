"""Upload audit helpers for authenticated IDS sample submission."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from ..services.ids_ai_analysis import is_llm_available
from ..utils.llm_client import chat

AUDIT_VERDICT_PASS = "pass"
AUDIT_VERDICT_REVIEW = "review"
AUDIT_VERDICT_QUARANTINE = "quarantine"

UPLOAD_ANALYSIS_MODE_STATIC = "static_only"
UPLOAD_ANALYSIS_MODE_AI = "llm_assisted"


class UploadAIAuditError(RuntimeError):
    """Raised when the configured upload audit cannot complete."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def _provider_name() -> str:
    provider = (settings.LLM_PROVIDER or "deepseek").strip().lower()
    return provider if provider in {"ollama", "openai", "deepseek", "kimi"} else "deepseek"


def _required_field(provider: str) -> str:
    return "LLM_API_KEY" if provider in {"openai", "deepseek", "kimi"} else "LLM_BASE_URL"


def _provider_label() -> str:
    provider = _provider_name()
    model = (settings.LLM_MODEL or "").strip()
    if provider == "openai" and (not model or model == "qwen2:7b"):
        model = "gpt-4.1-mini"
    elif provider == "deepseek" and (not model or model == "qwen2:7b"):
        model = "deepseek-chat"
    elif provider == "kimi" and (not model or model == "qwen2:7b"):
        model = "moonshot-v1-8k"
    elif not model:
        model = "qwen2:7b"
    return f"{provider}:{model}"


def upload_audit_mode() -> str:
    if settings.IDS_AI_ANALYSIS and is_llm_available():
        return UPLOAD_ANALYSIS_MODE_AI
    return UPLOAD_ANALYSIS_MODE_STATIC


def upload_audit_runtime_status() -> dict[str, Any]:
    provider = _provider_name()
    ai_ready = upload_audit_mode() == UPLOAD_ANALYSIS_MODE_AI
    if ai_ready:
        message = "当前已启用 AI 审计，上传会在静态预检基础上追加模型裁决。"
        mode_reason = "llm_ready"
    elif settings.IDS_AI_ANALYSIS:
        message = (
            f"当前未检测到可用的 {provider} AI 配置，上传先按静态审计模式运行；"
            f"补齐 {_required_field(provider)} 后会自动启用 AI 审计。"
        )
        mode_reason = "llm_not_ready"
    else:
        message = "当前 IDS_AI_ANALYSIS 未启用，上传按静态审计模式运行。"
        mode_reason = "ids_ai_disabled"

    return {
        "analysis_mode": UPLOAD_ANALYSIS_MODE_AI if ai_ready else UPLOAD_ANALYSIS_MODE_STATIC,
        "mode_label": "AI 审计" if ai_ready else "静态审计",
        "mode_reason": mode_reason,
        "provider": _provider_label() if ai_ready else "static-rules",
        "ai_available": ai_ready,
        "llm_used": ai_ready,
        "message": message,
    }


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if items:
            return items[:6]
    return default


def _normalize_risk_level(value: Any, default: str) -> str:
    risk = str(value or default).strip().lower()
    if risk in {"low", "medium", "high"}:
        return risk
    return default


def _normalize_verdict(value: Any, default: str) -> str:
    verdict = str(value or default).strip().lower()
    if verdict in {AUDIT_VERDICT_PASS, AUDIT_VERDICT_REVIEW, AUDIT_VERDICT_QUARANTINE}:
        return verdict
    return default


def _guardrail_verdict(
    heuristic_risk_level: str,
    indicators: list[dict[str, str]],
    binary_hint: bool,
) -> str:
    dangerous_codes = {
        "webshell_eval",
        "webshell_base64",
        "php_system",
        "php_assert",
        "script_download",
        "powershell",
        "cmd_shell",
        "wscript",
        "pe_header",
        "high_risk_ext",
    }
    codes = {item.get("code", "") for item in indicators}
    if heuristic_risk_level == "high" or codes & dangerous_codes:
        return AUDIT_VERDICT_QUARANTINE
    if binary_hint:
        return AUDIT_VERDICT_REVIEW
    if heuristic_risk_level == "medium" and indicators:
        return AUDIT_VERDICT_REVIEW
    return AUDIT_VERDICT_PASS


def _build_guardrail_result(
    *,
    file_name: str,
    heuristic_risk_level: str,
    indicators: list[dict[str, str]],
    binary_hint: bool,
) -> dict[str, Any]:
    verdict = _guardrail_verdict(heuristic_risk_level, indicators, binary_hint)
    evidence = [item.get("detail", "") for item in indicators if item.get("detail")][:6]
    if verdict == AUDIT_VERDICT_PASS:
        summary = f"{file_name} 未命中需要扣留的高风险静态特征。"
        actions = ["允许进入内部样本库并保留审计留痕。", "如需更高精度，可启用 AI 审计增强。"]
        confidence = 64 if heuristic_risk_level == "low" else 58
    elif verdict == AUDIT_VERDICT_REVIEW:
        summary = f"{file_name} 存在脚本、压缩包或其他可疑静态特征。"
        actions = ["继续保留在安全沙箱。", "复核来源、哈希和关联 IDS 事件后再决定是否释放。"]
        confidence = 74
    else:
        summary = f"{file_name} 命中了高风险执行或投递特征。"
        actions = ["立即扣留到安全沙箱。", "在断网环境补充离线分析后再做处置决定。"]
        confidence = 88 if heuristic_risk_level == "high" else 80

    return {
        "verdict": verdict,
        "risk_level": "high" if verdict == AUDIT_VERDICT_QUARANTINE else heuristic_risk_level,
        "confidence": confidence,
        "summary": summary,
        "evidence": evidence or ["本次静态预检未生成额外命中特征。"],
        "recommended_actions": actions,
    }


def _build_static_audit_result(
    *,
    file_name: str,
    heuristic_risk_level: str,
    indicators: list[dict[str, str]],
    binary_hint: bool,
) -> dict[str, Any]:
    guardrail = _build_guardrail_result(
        file_name=file_name,
        heuristic_risk_level=heuristic_risk_level,
        indicators=indicators,
        binary_hint=binary_hint,
    )

    if guardrail["verdict"] == AUDIT_VERDICT_PASS:
        summary = f"{file_name} 已按静态审计模式完成检查，未发现需要扣留的高风险特征。"
    elif guardrail["verdict"] == AUDIT_VERDICT_REVIEW:
        summary = f"{file_name} 已按静态审计模式完成检查，发现需要人工复核的可疑特征。"
    else:
        summary = f"{file_name} 已按静态审计模式完成检查，并被判定为高风险样本。"

    evidence = [
        "当前未启用可用的 AI 审计，系统已按扩展名、哈希、内容预览和静态特征执行检查。",
        *guardrail["evidence"],
    ][:6]
    actions = list(guardrail["recommended_actions"])
    if settings.IDS_AI_ANALYSIS:
        actions.append("如需启用 AI 审计，请在服务启动时输入密钥或补齐 LLM 配置。")

    return {
        "verdict": guardrail["verdict"],
        "risk_level": guardrail["risk_level"],
        "confidence": guardrail["confidence"],
        "summary": summary,
        "evidence": evidence,
        "reasons": evidence,
        "recommended_actions": actions[:4],
        "provider": "static-rules",
        "engine": "static_upload_ruleset",
        "analysis_mode": UPLOAD_ANALYSIS_MODE_STATIC,
        "mode_reason": "llm_not_ready" if settings.IDS_AI_ANALYSIS else "ids_ai_disabled",
        "ai_available": False,
        "llm_used": False,
        "static_risk_level": heuristic_risk_level,
        "heuristic_risk_level": heuristic_risk_level,
        "heuristic_verdict": guardrail["verdict"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_prompt(
    *,
    file_name: str,
    extension: str,
    size: int,
    sha256: str,
    heuristic_risk_level: str,
    indicators: list[dict[str, str]],
    content_preview: str,
    preview_truncated: bool,
    binary_hint: bool,
) -> str:
    indicator_text = "\n".join(
        f"- {item.get('code', '')}: {item.get('detail', '')}" for item in indicators[:12]
    ) or "- none"
    preview = (content_preview or "").strip() or "(binary or no printable preview)"
    return f"""你是独立 IDS 系统里的样本送检审计助手。请根据文件元数据、静态特征和内容摘录，对文件给出三类结论之一：
- pass: 可以进入内部样本库
- review: 暂不放行，进入安全沙箱等待人工复核
- quarantine: 明确高风险，必须扣留到安全沙箱

只输出严格 JSON，不要输出任何额外说明：
{{
  "verdict": "pass|review|quarantine",
  "risk_level": "low|medium|high",
  "confidence": 0,
  "summary": "1-2 句中文摘要",
  "evidence": ["证据1", "证据2"],
  "recommended_actions": ["动作1", "动作2"]
}}

裁决原则：
- 存在 WebShell、动态执行、下载投递、脚本宿主、二进制执行载荷等明显迹象时，必须选择 quarantine。
- 不确定但具备脚本、压缩、可疑文本片段时，选择 review。
- 只有普通文档、图片、常规文本且没有危险特征时，才能选择 pass。

文件信息：
- 文件名: {file_name}
- 扩展名: {extension or "(none)"}
- 大小: {size} bytes
- SHA-256: {sha256}
- 静态预检风险: {heuristic_risk_level}
- 预览是否截断: {"yes" if preview_truncated else "no"}
- 是否疑似二进制: {"yes" if binary_hint else "no"}
- 命中特征:
{indicator_text}

内容摘录：
{preview[:6000]}
"""


def audit_upload_payload(
    *,
    file_name: str,
    extension: str,
    size: int,
    sha256: str,
    heuristic_risk_level: str,
    indicators: list[dict[str, str]],
    content_preview: str,
    preview_truncated: bool,
    binary_hint: bool,
    trusted_format: bool = False,
    trusted_format_label: str = "",
) -> dict[str, Any]:
    if upload_audit_mode() != UPLOAD_ANALYSIS_MODE_AI:
        return _build_static_audit_result(
            file_name=file_name,
            heuristic_risk_level=heuristic_risk_level,
            indicators=indicators,
            binary_hint=binary_hint,
        )

    guardrail = _build_guardrail_result(
        file_name=file_name,
        heuristic_risk_level=heuristic_risk_level,
        indicators=indicators,
        binary_hint=binary_hint,
    )

    messages = [
        {"role": "system", "content": "你是安全文件审计助手，只输出 JSON。"},
        {
            "role": "user",
            "content": _build_prompt(
                file_name=file_name,
                extension=extension,
                size=size,
                sha256=sha256,
                heuristic_risk_level=heuristic_risk_level,
                indicators=indicators,
                content_preview=content_preview,
                preview_truncated=preview_truncated,
                binary_hint=binary_hint,
            ),
        },
    ]
    output = chat(messages)
    if not output:
        raise UploadAIAuditError("AI 审计调用失败，未收到模型响应。", code="upload_ai_no_response")

    payload = _extract_json(output)
    if not payload:
        raise UploadAIAuditError("AI 审计响应格式无效，无法解析 JSON。", code="upload_ai_invalid_response")

    verdict = _normalize_verdict(payload.get("verdict"), guardrail["verdict"])
    risk_level = _normalize_risk_level(payload.get("risk_level"), guardrail["risk_level"])
    confidence = max(
        0,
        min(100, int(payload.get("confidence", guardrail["confidence"]) or guardrail["confidence"])),
    )
    summary = str(payload.get("summary") or guardrail["summary"]).strip() or guardrail["summary"]
    evidence = _normalize_list(payload.get("evidence"), guardrail["evidence"])
    actions = _normalize_list(payload.get("recommended_actions"), guardrail["recommended_actions"])
    clean_trusted_format = trusted_format and heuristic_risk_level == "low" and not indicators and not binary_hint

    if clean_trusted_format:
        verdict = AUDIT_VERDICT_PASS
        risk_level = "low"
        confidence = max(confidence, 72)
        label = trusted_format_label or extension or "trusted file"
        summary = f"{file_name} 符合预期的 {label} 文件结构，未发现危险指征。"
        evidence = [
            f"文件签名与声明的 {label} 格式一致。",
            "未检测到脚本执行、下载投递、宏或可执行载荷等危险指征。",
        ]
        actions = [
            "允许进入内部样本库并保留审计留痕。",
            "如有需要，可在安全中心复核哈希与审计报告。",
        ]
    elif guardrail["verdict"] == AUDIT_VERDICT_QUARANTINE:
        verdict = AUDIT_VERDICT_QUARANTINE
        risk_level = "high"
    elif guardrail["verdict"] == AUDIT_VERDICT_REVIEW and verdict == AUDIT_VERDICT_PASS:
        verdict = AUDIT_VERDICT_REVIEW

    return {
        "verdict": verdict,
        "risk_level": risk_level,
        "confidence": confidence,
        "summary": summary,
        "evidence": evidence,
        "reasons": evidence,
        "recommended_actions": actions,
        "provider": _provider_label(),
        "engine": "upload_audit_llm",
        "analysis_mode": UPLOAD_ANALYSIS_MODE_AI,
        "mode_reason": "llm_ready",
        "ai_available": True,
        "llm_used": True,
        "static_risk_level": heuristic_risk_level,
        "heuristic_risk_level": heuristic_risk_level,
        "heuristic_verdict": guardrail["verdict"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
