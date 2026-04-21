"""LLM client wrappers for Ollama and OpenAI-compatible providers."""

from __future__ import annotations

import json
import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

API_KEY_PROVIDERS = {"openai", "deepseek", "kimi"}


def _provider_name() -> str:
    provider = (settings.LLM_PROVIDER or "").strip().lower()
    return provider or "deepseek"


def _provider_ready() -> bool:
    provider = _provider_name()
    if provider in API_KEY_PROVIDERS:
        return bool(settings.LLM_API_KEY and str(settings.LLM_API_KEY).strip())
    return bool(settings.LLM_BASE_URL and str(settings.LLM_BASE_URL).strip())


def _resolved_model() -> str:
    configured = (settings.LLM_MODEL or "").strip()
    provider = _provider_name()
    if configured and not (provider in API_KEY_PROVIDERS and configured == "qwen2:7b"):
        return configured
    if provider == "deepseek":
        return "deepseek-chat"
    if provider == "kimi":
        return "moonshot-v1-8k"
    if provider == "openai":
        return "gpt-4.1-mini"
    return configured or "qwen2:7b"


def _compatible_base_url() -> str:
    configured = (settings.LLM_BASE_URL or "").strip()
    if configured:
        return configured.rstrip("/")
    provider = _provider_name()
    if provider == "deepseek":
        return "https://api.deepseek.com"
    if provider == "kimi":
        return "https://api.moonshot.cn/v1"
    return "https://api.openai.com"


def _chat_completions_path(base: str) -> str:
    provider = _provider_name()
    if provider == "deepseek":
        return "/chat/completions"
    if provider == "kimi":
        return "/chat/completions" if base.endswith("/v1") else "/v1/chat/completions"
    return "/v1/chat/completions"


def _ollama_chat(messages: list[dict], model: str) -> str:
    url = f"{str(settings.LLM_BASE_URL).rstrip('/')}/api/chat"
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json={"model": model, "messages": messages, "stream": False})
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")


def _openai_compatible_chat(messages: list[dict], model: str) -> str:
    base = _compatible_base_url()
    url = base + _chat_completions_path(base)
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY or ''}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json={"model": model, "messages": messages})
        response.raise_for_status()
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def chat(messages: list[dict], model: str | None = None) -> str | None:
    """Call the configured LLM provider and return plain-text content."""
    if not _provider_ready():
        return None

    target_model = model or _resolved_model()
    provider = _provider_name()
    try:
        if provider == "ollama":
            return _ollama_chat(messages, target_model)
        if provider in API_KEY_PROVIDERS:
            return _openai_compatible_chat(messages, target_model)
    except Exception as exc:
        import traceback

        logger.warning("LLM request failed: %s\n%s", str(exc), traceback.format_exc())
        print(f"[LLM] request failed: {exc}")
    return None


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
) -> tuple[str | None, list[dict]]:
    """Call the configured LLM provider and parse tool calls when supported."""
    if not _provider_ready():
        return (None, [])

    target_model = model or _resolved_model()
    provider = _provider_name()
    if provider == "ollama":
        content = _ollama_chat(messages, target_model)
        return (content, []) if content else (None, [])

    base = _compatible_base_url()
    url = base + _chat_completions_path(base)
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY or ''}",
        "Content-Type": "application/json",
    }
    payload = {"model": target_model, "messages": messages, "tools": tools}

    try:
        with httpx.Client(timeout=90.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = []
        for raw_call in raw_tool_calls:
            function_call = raw_call.get("function", {})
            arguments_raw = function_call.get("arguments", "{}")
            try:
                arguments = json.loads(arguments_raw) if isinstance(arguments_raw, str) else arguments_raw
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                {
                    "id": raw_call.get("id", ""),
                    "name": function_call.get("name", ""),
                    "arguments": arguments,
                }
            )
        return (content.strip() if content else None, tool_calls)
    except Exception as exc:
        import traceback

        logger.warning("LLM tool request failed: %s\n%s", str(exc), traceback.format_exc())
        print(f"[LLM] tool request failed: {exc}")
        return (None, [])
