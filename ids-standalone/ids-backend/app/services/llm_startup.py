"""Interactive startup checks for optional IDS AI readiness."""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path
from typing import Any

from ..config import settings
from .ids_ai_analysis import is_llm_available
from .upload_ai_audit import upload_audit_runtime_status

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"

_PROVIDER_DEFAULTS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
    },
    "kimi": {
        "model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
    },
    "openai": {
        "model": "gpt-4.1-mini",
        "base_url": "https://api.openai.com",
    },
    "ollama": {
        "model": "qwen2:7b",
        "base_url": "http://127.0.0.1:11434",
    },
}

_INTERACTIVE_PROVIDERS = {"deepseek", "kimi"}


def _provider_name() -> str:
    provider = (settings.LLM_PROVIDER or "deepseek").strip().lower()
    return provider if provider in _PROVIDER_DEFAULTS else "deepseek"


def _required_field(provider: str) -> str:
    return "LLM_API_KEY" if provider in {"openai", "deepseek", "kimi"} else "LLM_BASE_URL"


def _effective_base_url(provider: str) -> str:
    configured = (settings.LLM_BASE_URL or "").strip()
    if configured:
        return configured
    return _PROVIDER_DEFAULTS[provider]["base_url"]


def _resolved_model(provider: str) -> str:
    configured = (settings.LLM_MODEL or "").strip()
    if configured and not (provider in {"openai", "deepseek", "kimi"} and configured == "qwen2:7b"):
        return configured
    return _PROVIDER_DEFAULTS[provider]["model"]


def llm_runtime_status() -> dict[str, Any]:
    provider = _provider_name()
    ready = is_llm_available()
    upload_status = upload_audit_runtime_status()
    return {
        "ready": ready,
        "provider": provider,
        "model": _resolved_model(provider),
        "required_field": _required_field(provider),
        "effective_base_url": _effective_base_url(provider),
        "message": (
            "IDS AI audit is ready."
            if ready
            else f"IDS AI audit is not ready. Missing {_required_field(provider)} for provider={provider}."
        ),
        "upload_audit_mode": upload_status["analysis_mode"],
        "upload_audit_label": upload_status["mode_label"],
        "upload_audit_message": upload_status["message"],
        "upload_audit_mode_reason": upload_status["mode_reason"],
    }


def _write_env_updates(updates: dict[str, str]) -> None:
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key, _, _value = line.partition("=")
        normalized_key = key.strip()
        if normalized_key in updates:
            new_lines.append(f"{normalized_key}={updates[normalized_key]}")
            seen.add(normalized_key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _apply_runtime_updates(updates: dict[str, str]) -> None:
    for key, value in updates.items():
        os.environ[key] = value
        normalized = value.strip()
        setattr(settings, key, normalized or None)


def _prompt_secret(prompt: str) -> str:
    try:
        return getpass.getpass(prompt).strip()
    except Exception:
        return input(prompt).strip()


def _prompt_enable_now(provider: str) -> bool:
    answer = input(
        f"当前未检测到可用的 AI 配置（当前默认提供方: {provider}）。是否现在启用 AI 审计？[y/N]: "
    ).strip().lower()
    return answer in {"y", "yes"}


def _prompt_provider(provider: str) -> str:
    default_provider = provider if provider in _INTERACTIVE_PROVIDERS else "deepseek"
    answer = input(
        f"请选择 AI 模型提供方，直接回车沿用当前值 [{default_provider}]，可选 deepseek / kimi: "
    ).strip().lower()
    if not answer:
        return default_provider
    if answer in _INTERACTIVE_PROVIDERS:
        return answer
    print(f"[startup] 未识别的提供方 {answer}，继续沿用 {default_provider}。")
    return default_provider


def _prompt_updates(provider: str) -> dict[str, str] | None:
    defaults = _PROVIDER_DEFAULTS[provider]
    api_key = _prompt_secret(f"请输入 {provider} API Key: ")
    if not api_key:
        return None

    print(
        "[startup] 已自动设置默认连接参数: "
        f"provider={provider}, model={defaults['model']}, base={defaults['base_url']}"
    )
    return {
        "LLM_PROVIDER": provider,
        "LLM_API_KEY": api_key,
        "LLM_BASE_URL": defaults["base_url"],
        "LLM_MODEL": defaults["model"],
    }


def ensure_llm_ready_for_ids() -> dict[str, Any]:
    status = llm_runtime_status()
    if str(os.environ.get("IDS_SKIP_LLM_STARTUP_PROMPT", "")).strip() == "1":
        return status
    if status["ready"] or not settings.IDS_AI_ANALYSIS:
        return status

    if not sys.stdin or not sys.stdin.isatty():
        print(
            "[startup] "
            f"{status['upload_audit_message']} 当前启动环境不可交互。"
            f"如需启用 AI 审计，请先在 backend/.env 中补齐 {status['required_field']}。"
        )
        return llm_runtime_status()

    if not _prompt_enable_now(str(status["provider"])):
        print("[startup] 跳过 AI 配置，系统继续以静态审计模式启动。")
        return llm_runtime_status()

    provider = _prompt_provider(str(status["provider"]))
    updates = _prompt_updates(provider)
    if not updates:
        print("[startup] 未提供完整的 AI 配置，系统继续以静态审计模式启动。")
        return llm_runtime_status()

    _write_env_updates(updates)
    _apply_runtime_updates(updates)

    refreshed = llm_runtime_status()
    if refreshed["ready"]:
        print(
            "[startup] IDS AI audit configured: "
            f"provider={refreshed['provider']}, model={refreshed['model']}, "
            f"base={refreshed['effective_base_url'] or '-'}"
        )
    else:
        print(f"[startup] {refreshed['upload_audit_message']} 系统继续以静态审计模式启动。")
    return refreshed
