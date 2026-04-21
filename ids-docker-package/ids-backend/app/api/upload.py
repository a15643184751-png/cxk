"""Authenticated sample-submission and sandbox analysis endpoints."""

from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .deps import IntegrationPrincipal, require_roles, require_roles_or_integration
from ..config import settings
from ..database import get_db
from ..models.ids_event import IDSEvent
from ..models.user import User
from ..services.audit import write_audit_log
from ..services.ids_ingestion import SOURCE_CUSTOM_PROJECT, TEST_EVENT_ORIGIN, apply_source_metadata, build_correlation_key, build_event_fingerprint
from ..services.ids_operator_hub import auto_dispatch_notifications_for_event, serialize_notification_event
from ..services.upload_ai_audit import AUDIT_VERDICT_PASS, AUDIT_VERDICT_QUARANTINE, AUDIT_VERDICT_REVIEW, UploadAIAuditError, audit_upload_payload

router = APIRouter(prefix="/upload", tags=["upload"])

ACCEPTED_DIR = Path(settings.IDS_ACCEPTED_UPLOAD_DIR)
QUARANTINE_DIR = Path(settings.IDS_QUARANTINE_DIR)
REPORT_DIR = Path(settings.IDS_REPORT_DIR)
for _path in (ACCEPTED_DIR, QUARANTINE_DIR, REPORT_DIR):
    _path.mkdir(parents=True, exist_ok=True)

_admin = require_roles("ids_admin")
_ids_user_or_integration = require_roles_or_integration("ids_admin", "ids_operator", "ids_auditor", "ids_viewer")
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg", ".conf"}
IMAGE_EXTENSIONS = {".png": "PNG image", ".jpg": "JPEG image", ".jpeg": "JPEG image", ".gif": "GIF image", ".webp": "WEBP image", ".bmp": "BMP image"}
OPENXML_MAIN_PARTS = {".docx": "word/document.xml", ".xlsx": "xl/workbook.xml", ".pptx": "ppt/presentation.xml"}
OLE_EXTENSIONS = {".doc", ".xls", ".ppt"}
HIGH_RISK_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".scr", ".com", ".dll", ".msi", ".hta", ".jar", ".sh"}
MEDIUM_RISK_EXTENSIONS = {".php", ".jsp", ".asp", ".aspx", ".js", ".vbs", ".zip", ".rar", ".7z", ".html", ".htm"}
SCRIPT_EXTENSIONS = {".php", ".jsp", ".asp", ".aspx", ".js", ".vbs", ".ps1", ".bat", ".cmd", ".sh", ".hta"}
ARCHIVE_SCRIPT_EXTENSIONS = HIGH_RISK_EXTENSIONS | SCRIPT_EXTENSIONS | {".php", ".jsp", ".asp", ".aspx", ".html", ".htm"}
HIGH_RISK_CODES = {"webshell_eval", "webshell_base64", "php_system", "php_assert", "powershell", "cmd_shell", "wscript", "script_download", "pe_header", "high_risk_ext", "office_macro", "archive_script_entry", "pdf_javascript", "pdf_embedded_file"}
MEDIUM_RISK_CODES = {"medium_risk_ext", "signature_mismatch", "php_tag", "unknown_binary", "script_disguised_text"}
PATTERNS: list[tuple[str, str, str]] = [
    ("webshell_eval", "Detected eval execution fragment", r"\beval\s*\("),
    ("webshell_base64", "Detected base64 decode fragment", r"base64_decode\s*\("),
    ("php_system", "Detected command execution function", r"\b(?:system|shell_exec|passthru|exec|popen|proc_open)\s*\("),
    ("php_assert", "Detected assert execution function", r"\bassert\s*\("),
    ("powershell", "Detected PowerShell command", r"powershell(?:\.exe)?"),
    ("cmd_shell", "Detected command shell fragment", r"\bcmd(?:\.exe)?\b|/c\s"),
    ("wscript", "Detected Windows Script Host fragment", r"\b(?:wscript|cscript)\b"),
    ("script_download", "Detected external download command", r"\b(?:curl|wget|invoke-webrequest|bitsadmin|certutil)\b|https?://"),
    ("php_tag", "Detected PHP script tag", r"<\?php"),
]


class QuarantineAnalyzeRequest(BaseModel):
    saved_as: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _normalize_filename(name: str) -> str:
    safe = Path(name or "unnamed").name.strip() or "unnamed"
    return re.sub(r"[\r\n\t]", "_", safe)[:180]


def _saved_name(name: str) -> str:
    return f"{uuid.uuid4().hex[:8]}_{_normalize_filename(name)}"


def _safe_child_path(root: Path, name: str) -> Path | None:
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    path = (root / Path(name).name).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def _report_path(saved_as: str) -> Path | None:
    return _safe_child_path(REPORT_DIR, f"{saved_as}.json")


def _client_public_base(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    if forwarded_host:
        return f"{forwarded_proto or 'http'}://{forwarded_host.split(',')[0].strip()}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _accepted_url(request: Request, saved_as: str) -> str:
    return f"{_client_public_base(request)}/uploads/accepted/{saved_as}"


def _quarantine_file_url(request: Request, saved_as: str) -> str:
    return f"{_client_public_base(request)}/api/upload/quarantine/file/{saved_as}"


def _request_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client and request.client.host else "0.0.0.0")[:64]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def _with_audit_compat(audit: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(audit or {})
    payload.setdefault("recommended_actions", [])
    payload.setdefault("recommended_action", (payload.get("recommended_actions") or [""])[0])
    payload.setdefault("analysis_mode_label", "AI audit" if payload.get("analysis_mode") == "llm_assisted" else "Static audit")
    payload.setdefault("reasons", payload.get("evidence") or [])
    if "llm_available" not in payload and "ai_available" in payload:
        payload["llm_available"] = bool(payload.get("ai_available"))
    return payload


def _detect_signature(content: bytes) -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if content.startswith(b"%PDF-"):
        return "pdf"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith(b"BM"):
        return "bmp"
    if content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    if content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"
    if content.startswith(b"MZ"):
        return "pe"
    return "unknown"


def _looks_binary(content: bytes) -> bool:
    sample = content[:4096]
    if not sample:
        return False
    for encoding in ("utf-8-sig", "utf-16", "utf-32", "gb18030"):
        try:
            decoded = sample.decode(encoding)
        except UnicodeDecodeError:
            continue
        normalized = decoded.replace("\ufeff", "")
        if not normalized:
            return False
        printable = sum(1 for char in normalized if char.isprintable() or char in "\t\r\n")
        visible = sum(1 for char in normalized if not char.isspace())
        if visible and printable / len(normalized) >= 0.85:
            return False
    if b"\x00" in sample:
        return True
    printable = sum(1 for byte in sample if byte in b"\t\n\r" or 32 <= byte <= 126)
    return printable / max(len(sample), 1) < 0.72


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-32", "utf-8", "gb18030", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _normalize_preview(text: str, *, limit: int = 2400) -> tuple[str, bool]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if len(normalized) <= limit:
        return normalized, False
    return normalized[:limit].rstrip(), True


def _extract_printable_strings(content: bytes, *, limit: int = 2400) -> tuple[str, bool]:
    decoded = _decode_text(content[:16384])
    matches = re.findall(r"[A-Za-z0-9_\-./:@]{4,}", decoded)
    return _normalize_preview(" ".join(matches[:200]), limit=limit)


def _collect_xml_text(raw_xml: bytes) -> str:
    try:
        root = ET.fromstring(raw_xml)
        text = " ".join(part.strip() for part in root.itertext() if part and part.strip())
        if text.strip():
            return text
    except ET.ParseError:
        pass
    return re.sub(r"<[^>]+>", " ", raw_xml.decode("utf-8", errors="ignore"))


def _zip_entries(content: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            return archive.namelist()
    except zipfile.BadZipFile:
        return []

def _preview_and_entries(file_name: str, extension: str, signature: str, content: bytes) -> tuple[str, bool, list[str]]:
    zip_entries: list[str] = []
    if extension in OPENXML_MAIN_PARTS and signature == "zip":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                zip_entries = archive.namelist()
                targets: list[str] = []
                if extension == ".docx":
                    targets = [name for name in zip_entries if name == "word/document.xml" or name.startswith("word/header")]
                elif extension == ".xlsx":
                    targets = [name for name in zip_entries if name in {"xl/sharedStrings.xml", "xl/workbook.xml"}]
                elif extension == ".pptx":
                    slides = sorted(name for name in zip_entries if name.startswith("ppt/slides/slide"))[:3]
                    targets = ["ppt/presentation.xml", *slides]
                chunks = []
                for name in targets[:6]:
                    try:
                        chunks.append(_collect_xml_text(archive.read(name)))
                    except KeyError:
                        continue
                preview, truncated = _normalize_preview(" ".join(chunks))
                if preview:
                    return preview, truncated, zip_entries
                return f"Detected valid {extension.lstrip('.')} OpenXML container with {len(zip_entries)} entries.", False, zip_entries
        except zipfile.BadZipFile:
            return "", False, []
    if extension in TEXT_EXTENSIONS or (signature == "unknown" and not _looks_binary(content)):
        preview, truncated = _normalize_preview(_decode_text(content[:16384]))
        return preview or f"{file_name} contains no printable preview text.", truncated, zip_entries
    if signature == "pdf":
        preview, truncated = _extract_printable_strings(content)
        return preview or "Detected PDF document. No readable text was extracted from the first-page sample.", truncated, zip_entries
    if signature == "zip":
        zip_entries = _zip_entries(content)
        listed = ", ".join(zip_entries[:8])
        return (f"ZIP container entries: {listed}" if listed else "ZIP container detected."), len(zip_entries) > 8, zip_entries
    if signature == "ole":
        return "Detected OLE compound-document container.", False, zip_entries
    if extension in IMAGE_EXTENSIONS and signature == extension.lstrip(".").replace("jpg", "jpeg"):
        return f"Detected valid {IMAGE_EXTENSIONS[extension]}. Binary image formats do not expose a text preview.", False, zip_entries
    if signature in {"png", "jpeg", "gif", "webp", "bmp"}:
        return f"Detected binary {signature.upper()} payload.", False, zip_entries
    if signature == "pe":
        return "Detected Windows PE executable header.", False, zip_entries
    preview, truncated = _extract_printable_strings(content)
    return preview or f"{file_name} is a binary payload without stable text preview.", truncated, zip_entries


def _signature_matches(extension: str, signature: str, zip_entries: list[str]) -> bool:
    if extension in TEXT_EXTENSIONS:
        return signature == "unknown"
    if extension in IMAGE_EXTENSIONS:
        return signature == extension.lstrip(".").replace("jpg", "jpeg")
    if extension == ".pdf":
        return signature == "pdf"
    if extension == ".zip":
        return signature == "zip"
    if extension in OPENXML_MAIN_PARTS:
        return signature == "zip" and OPENXML_MAIN_PARTS[extension] in zip_entries
    if extension in OLE_EXTENSIONS:
        return signature == "ole"
    if extension in HIGH_RISK_EXTENSIONS:
        return signature in {"pe", "ole"}
    return signature == "unknown"


def _add_indicator(indicators: list[dict[str, str]], code: str, detail: str) -> None:
    if any(item["code"] == code for item in indicators):
        return
    indicators.append({"code": code, "detail": detail})


def _inspect_upload(file_name: str, content: bytes) -> dict[str, Any]:
    extension = Path(file_name).suffix.lower()
    signature = _detect_signature(content)
    preview, preview_truncated, zip_entries = _preview_and_entries(file_name, extension, signature, content)
    indicators: list[dict[str, str]] = []

    if extension in HIGH_RISK_EXTENSIONS:
        _add_indicator(indicators, "high_risk_ext", f"Extension {extension or '(none)'} is a high-risk executable or script type")
    elif extension in MEDIUM_RISK_EXTENSIONS:
        _add_indicator(indicators, "medium_risk_ext", f"Extension {extension or '(none)'} is a script or archive type")
    if signature == "pe":
        _add_indicator(indicators, "pe_header", "Detected Windows PE executable header")
    if signature == "zip":
        lowered = [name.lower() for name in zip_entries]
        if any(name.endswith("vbaproject.bin") for name in lowered):
            _add_indicator(indicators, "office_macro", "Detected VBA macro payload inside OpenXML container")
        suspicious = [name for name in zip_entries if Path(name).suffix.lower() in ARCHIVE_SCRIPT_EXTENSIONS]
        if suspicious:
            _add_indicator(indicators, "archive_script_entry", f"Detected script or executable entries inside archive: {', '.join(suspicious[:4])}")
    if not _signature_matches(extension, signature, zip_entries):
        if not (signature == "unknown" and extension in TEXT_EXTENSIONS and not _looks_binary(content)):
            _add_indicator(indicators, "signature_mismatch", f"Content signature {signature} does not match declared extension {extension or '(none)'}")

    if extension in SCRIPT_EXTENSIONS or extension in HIGH_RISK_EXTENSIONS:
        text = _decode_text(content[:65536]).lower()
        for code, detail, pattern in PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                _add_indicator(indicators, code, detail)
    elif extension in TEXT_EXTENSIONS and not _looks_binary(content):
        head = _decode_text(content[:4096]).lstrip().lower()
        if head.startswith(("<?php", "#!/bin/", "#!/usr/bin/", "@echo off", "powershell", "<script")):
            _add_indicator(indicators, "script_disguised_text", "Plain-text extension starts with a script entry point")
    elif signature == "pdf":
        head = content[:262144].decode("latin-1", errors="ignore").lower()
        if re.search(r"/(?:javascript|js)\b", head):
            _add_indicator(indicators, "pdf_javascript", "Detected PDF JavaScript marker")
        if re.search(r"/(?:embeddedfile|launch|openaction)\b", head):
            _add_indicator(indicators, "pdf_embedded_file", "Detected PDF embedded-file or launch marker")

    trusted_format = False
    trusted_format_label = ""
    if extension in IMAGE_EXTENSIONS and _signature_matches(extension, signature, zip_entries):
        trusted_format = True
        trusted_format_label = IMAGE_EXTENSIONS[extension]
    elif extension == ".pdf" and signature == "pdf":
        trusted_format = True
        trusted_format_label = "PDF document"
    elif extension in OPENXML_MAIN_PARTS and _signature_matches(extension, signature, zip_entries):
        trusted_format = not any(item["code"] in {"office_macro", "archive_script_entry"} for item in indicators)
        trusted_format_label = f"{extension.lstrip('.')} OpenXML document"
    elif extension in OLE_EXTENSIONS and signature == "ole":
        trusted_format = True
        trusted_format_label = f"{extension.lstrip('.')} OLE document"
    elif extension in TEXT_EXTENSIONS and signature == "unknown" and not _looks_binary(content):
        trusted_format = True
        trusted_format_label = "plain text"

    binary_hint = _looks_binary(content) and not trusted_format
    if binary_hint and signature == "unknown":
        _add_indicator(indicators, "unknown_binary", "Content looks like unknown binary payload and does not match a trusted format")
    codes = {item["code"] for item in indicators}
    if codes & HIGH_RISK_CODES:
        level = "high"
    elif codes & MEDIUM_RISK_CODES or binary_hint:
        level = "medium"
    else:
        level = "low"
    return {
        "extension": extension,
        "signature": signature,
        "content_preview": preview,
        "preview_truncated": preview_truncated,
        "indicators": indicators[:12],
        "heuristic_risk_level": level,
        "binary_hint": binary_hint,
        "trusted_format": trusted_format,
        "trusted_format_label": trusted_format_label,
    }


def _load_report(saved_as: str) -> dict[str, Any] | None:
    path = _report_path(saved_as)
    if not path or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_report(saved_as: str, payload: dict[str, Any]) -> None:
    path = _report_path(saved_as)
    if not path:
        raise HTTPException(status_code=400, detail="Invalid saved_as")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _report_risk_level(audit: dict[str, Any], profile: dict[str, Any]) -> str:
    risk = str(audit.get("risk_level") or profile.get("heuristic_risk_level") or "low").lower()
    return risk if risk in {"low", "medium", "high"} else "low"


def _decision_source(audit: dict[str, Any]) -> str:
    return "llm" if audit.get("llm_used") else "static"


def _hold_reason_summary(file_name: str, audit: dict[str, Any], profile: dict[str, Any]) -> str:
    verdict = str(audit.get("verdict") or AUDIT_VERDICT_REVIEW)
    indicators = profile.get("indicators") or []
    indicator_text = ", ".join(str(item.get("code") or "") for item in indicators[:4] if isinstance(item, dict) and item.get("code"))
    summary = str(audit.get("summary") or "").strip()
    if verdict == AUDIT_VERDICT_PASS:
        return summary or f"{file_name} passed the static upload checks and was released."
    if indicator_text:
        return summary or f"{file_name} was held because the static scanner matched {indicator_text}."
    if verdict == AUDIT_VERDICT_QUARANTINE:
        return summary or f"{file_name} was held because the static scanner marked it as high risk."
    return summary or f"{file_name} was held for manual review after the upload scanner found suspicious traits."


def _build_decision_basis(file_name: str, profile: dict[str, Any], audit: dict[str, Any], *, linked_event_id: int | None = None) -> dict[str, Any]:
    verdict = str(audit.get("verdict") or AUDIT_VERDICT_REVIEW)
    risk_level = _report_risk_level(audit, profile)
    blocked = verdict != AUDIT_VERDICT_PASS
    hold_reason = _hold_reason_summary(file_name, audit, profile)
    indicators = []
    for item in (profile.get("indicators") or [])[:12]:
        if isinstance(item, dict):
            indicators.append(
                {
                    "code": str(item.get("code") or "")[:64],
                    "detail": str(item.get("detail") or "")[:255],
                }
            )
    return {
        "final_source": _decision_source(audit),
        "analysis_mode": str(audit.get("analysis_mode") or "static_only")[:32],
        "analysis_mode_label": str(audit.get("analysis_mode_label") or "Static audit")[:64],
        "mode_reason": str(audit.get("mode_reason") or "")[:64],
        "verdict": verdict[:32],
        "blocked": blocked,
        "risk_level": risk_level,
        "confidence": max(0, min(100, int(audit.get("confidence") or 0))),
        "hold_reason_summary": hold_reason[:1000],
        "indicator_count": len(indicators),
        "matched_indicators": indicators,
        "llm_used": bool(audit.get("llm_used")),
        "ai_available": bool(audit.get("ai_available") or audit.get("llm_available")),
        "provider": str(audit.get("provider") or audit.get("engine") or "static-rules")[:128],
        "recommended_actions": [
            str(action).strip()[:255]
            for action in (audit.get("recommended_actions") or [])
            if str(action).strip()
        ][:5],
        "reasons": [
            str(reason).strip()[:255]
            for reason in (audit.get("reasons") or audit.get("evidence") or [])
            if str(reason).strip()
        ][:6],
        "static_risk_level": str(audit.get("static_risk_level") or profile.get("heuristic_risk_level") or risk_level)[:32],
        "heuristic_risk_level": str(audit.get("heuristic_risk_level") or profile.get("heuristic_risk_level") or risk_level)[:32],
        "heuristic_verdict": str(audit.get("heuristic_verdict") or verdict)[:32],
        "linked_event_id": int(linked_event_id or audit.get("linked_event_id") or 0) or None,
    }


def _build_report_payload(saved_as: str, file_name: str, size: int, sha256_value: str, storage_location: str, profile: dict[str, Any], audit: dict[str, Any], *, existing: dict[str, Any] | None = None, sections: list[dict[str, str]] | None = None) -> dict[str, Any]:
    existing_payload = existing or {}
    updated_at = _now_iso()
    audit_payload = _with_audit_compat(audit)
    linked_event_id = (
        existing_payload.get("decision_basis", {}).get("linked_event_id")
        if isinstance(existing_payload.get("decision_basis"), dict)
        else None
    )
    decision_basis = _build_decision_basis(file_name, profile, audit_payload, linked_event_id=linked_event_id)
    return {
        "saved_as": saved_as,
        "file_name": _normalize_filename(file_name),
        "original_name": _normalize_filename(file_name),
        "generated_at": existing_payload.get("generated_at") or updated_at,
        "last_updated_at": updated_at,
        "analysis_generated_at": updated_at if sections is not None else existing_payload.get("analysis_generated_at"),
        "size": int(size),
        "extension": str(profile.get("extension") or Path(file_name).suffix.lower()),
        "sha256": sha256_value,
        "risk_level": _report_risk_level(audit_payload, profile),
        "indicator_count": len(profile.get("indicators") or []),
        "indicators": profile.get("indicators") or [],
        "storage_location": storage_location,
        "analysis_source": "sandbox_analysis" if sections is not None else "upload_gate",
        "audit": audit_payload,
        "decision_basis": decision_basis,
        "sections": sections if sections is not None else (existing_payload.get("sections") or []),
    }

def _build_report_sections(saved_as: str, file_name: str, size: int, sha256_value: str, storage_location: str, profile: dict[str, Any], audit: dict[str, Any]) -> list[dict[str, str]]:
    indicators = profile.get("indicators") or []
    basis = _build_decision_basis(file_name, profile, audit)
    indicator_text = "\n".join(f"- {item['code']}: {item['detail']}" for item in indicators) if indicators else "- No dangerous indicators were detected."
    actions = basis.get("recommended_actions") or []
    action_text = "\n".join(f"- {item}" for item in actions) if actions else "- No follow-up action was generated."
    preview_text = str(profile.get("content_preview") or "No preview captured.")
    return [
        {
            "title": "Why This File Was Held",
            "body": (
                f"Verdict: {basis.get('verdict')}\n"
                f"Blocked: {'yes' if basis.get('blocked') else 'no'}\n"
                f"Analysis source: {basis.get('final_source')}\n"
                f"Analysis mode: {basis.get('analysis_mode_label') or basis.get('analysis_mode')}\n"
                f"Mode reason: {basis.get('mode_reason') or '-'}\n"
                f"Confidence: {basis.get('confidence')}\n"
                f"Summary: {basis.get('hold_reason_summary') or '-'}"
            ),
        },
        {
            "title": "Sample Overview",
            "body": (
                f"Saved as: {saved_as}\n"
                f"Original name: {file_name}\n"
                f"Size: {size} bytes\n"
                f"Extension: {profile.get('extension') or '(none)'}\n"
                f"SHA-256: {sha256_value}\n"
                f"Storage: {storage_location}"
            ),
        },
        {
            "title": "Static Signals",
            "body": (
                f"Signature: {profile.get('signature')}\n"
                f"Trusted format: {'yes' if profile.get('trusted_format') else 'no'}\n"
                f"Trusted label: {profile.get('trusted_format_label') or '-'}\n"
                f"Heuristic risk: {basis.get('heuristic_risk_level') or '-'}\n"
                f"Heuristic verdict: {basis.get('heuristic_verdict') or '-'}\n"
                f"Indicators:\n{indicator_text}"
            ),
        },
        {
            "title": "AI And Review Analysis",
            "body": (
                f"Provider: {basis.get('provider') or '-'}\n"
                f"LLM used: {'yes' if basis.get('llm_used') else 'no'}\n"
                f"AI available: {'yes' if basis.get('ai_available') else 'no'}\n"
                f"Risk level: {audit.get('risk_level') or '-'}\n"
                f"Summary: {audit.get('summary') or '-'}\n"
                f"Reasons:\n"
                + ("\n".join(f"- {item}" for item in (basis.get('reasons') or [])) if basis.get("reasons") else "- No additional reasons were returned.")
            ),
        },
        {
            "title": "Preview And Disposition",
            "body": (
                f"Preview truncated: {'yes' if profile.get('preview_truncated') else 'no'}\n"
                f"Preview: {preview_text}\n"
                f"Actions:\n{action_text}"
            ),
        },
    ]


def _ids_score(report: dict[str, Any]) -> int:
    audit = report.get("audit") if isinstance(report.get("audit"), dict) else {}
    verdict = str(audit.get("verdict") or "")
    confidence = max(0, min(100, int(audit.get("confidence") or 0)))
    if verdict == AUDIT_VERDICT_QUARANTINE:
        return max(82, confidence)
    if verdict == AUDIT_VERDICT_REVIEW:
        return max(60, confidence)
    return max(20, min(55, confidence))


def _actor_fields(current_user: User | IntegrationPrincipal | None) -> tuple[int | None, str, str]:
    if current_user is None:
        return None, "ids_system", "system"
    if isinstance(current_user, IntegrationPrincipal):
        label = (current_user.source_system or current_user.subject or "site-integration").strip()[:64]
        return None, label, current_user.role
    return current_user.id, (current_user.real_name or current_user.username or "ids_admin")[:64], (current_user.role or "ids_admin")[:64]


def _write_ids_log(db: Session, *, current_user: User | IntegrationPrincipal | None, action: str, target_type: str, target_id: str, detail: str) -> None:
    user_id, user_name, user_role = _actor_fields(current_user)
    write_audit_log(db, user_id=user_id, user_name=user_name, user_role=user_role, action=action, target_type=target_type, target_id=target_id, detail=detail[:512])


def _run_upload_audit(file_name: str, content: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = _inspect_upload(file_name, content)
    audit = audit_upload_payload(
        file_name=file_name,
        extension=str(profile.get("extension") or ""),
        size=len(content),
        sha256=_sha256(content),
        heuristic_risk_level=str(profile.get("heuristic_risk_level") or "low"),
        indicators=profile.get("indicators") or [],
        content_preview=str(profile.get("content_preview") or ""),
        preview_truncated=bool(profile.get("preview_truncated")),
        binary_hint=bool(profile.get("binary_hint")),
        trusted_format=bool(profile.get("trusted_format")),
        trusted_format_label=str(profile.get("trusted_format_label") or ""),
    )
    return profile, _with_audit_compat(audit)


def _sync_ids_event_from_report(db: Session, request: Request, report: dict[str, Any]) -> int:
    audit = report.get("audit") if isinstance(report.get("audit"), dict) else {}
    decision_basis = report.get("decision_basis") if isinstance(report.get("decision_basis"), dict) else {}
    linked_event_id = int(audit.get("linked_event_id") or 0)
    event = db.query(IDSEvent).filter(IDSEvent.id == linked_event_id).first() if linked_event_id else None
    created_at = _now()
    if not event:
        event = IDSEvent(created_at=created_at)
        db.add(event)
    saved_as = str(report.get("saved_as") or "")
    file_name = str(report.get("file_name") or saved_as)
    indicators = report.get("indicators") if isinstance(report.get("indicators"), list) else []
    indicator_codes = ", ".join(item.get("code", "") for item in indicators[:4] if isinstance(item, dict) and item.get("code")) or "upload_audit_gate"
    event.client_ip = _request_ip(request)
    event.attack_type = "malware"
    event.signature_matched = indicator_codes[:128]
    event.method = "POST"
    event.path = "/api/ids/detection/sample-submit"
    event.body_snippet = (f"saved_as={saved_as}; sha256={report.get('sha256') or ''}; original_name={file_name}; verdict={audit.get('verdict') or ''}")[:2000]
    event.user_agent = (request.headers.get("user-agent") or "")[:512]
    event.blocked = 1
    event.firewall_rule = "upload_audit_gate"
    event.archived = 0
    event.status = "investigating"
    event.review_note = str(decision_basis.get("hold_reason_summary") or "Created by upload audit quarantine flow.")[:2000]
    event.action_taken = f"upload::{audit.get('verdict') or AUDIT_VERDICT_REVIEW}::{saved_as}"[:128]
    event.response_result = str(audit.get("verdict") or "")
    event.response_detail = str(decision_basis.get("hold_reason_summary") or audit.get("summary") or "")[:8000]
    event.risk_score = _ids_score(report)
    event.confidence = max(0, min(100, int(audit.get("confidence") or 0)))
    event.hit_count = max(1, int(report.get("indicator_count") or 0))
    event.detect_detail = json.dumps(report, ensure_ascii=False)
    event.ai_risk_level = str(audit.get("risk_level") or report.get("risk_level") or "")
    event.ai_confidence = max(0, min(100, int(audit.get("confidence") or 0))) if audit.get("llm_used") else 0
    event.ai_analysis = str(audit.get("summary") or "")[:8000] if audit.get("llm_used") else ""
    event.ai_analyzed_at = _now() if audit.get("llm_used") else None
    fingerprint = build_event_fingerprint(event.client_ip or "", event.method or "", event.path or "", event.attack_type or "", "upload_ai_gate")
    correlation = build_correlation_key(created_at, event.client_ip or "", event.attack_type or "", "upload_ai_gate")
    apply_source_metadata(event, event_origin=TEST_EVENT_ORIGIN, source_classification=SOURCE_CUSTOM_PROJECT, detector_family="sample_submission", detector_name="upload_ai_gate", source_rule_id="upload_ai_gate", source_rule_name="upload_ai_gate", source_version=str(audit.get("provider") or audit.get("engine") or "upload_audit"), source_freshness="current", occurred_at=created_at, event_fingerprint=fingerprint, correlation_key=correlation)
    db.flush()
    report["audit"]["linked_event_id"] = int(event.id)
    event.detect_detail = json.dumps(report, ensure_ascii=False)
    return int(event.id)


@router.post("")
async def submit_detection_sample(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | IntegrationPrincipal = Depends(_ids_user_or_integration),
):
    file_name = _normalize_filename(file.filename or "unnamed")
    content = await file.read()
    try:
        profile, audit = _run_upload_audit(file_name, content)
    except UploadAIAuditError as exc:
        _write_ids_log(db, current_user=current_user, action="ids_sample_submit_rejected", target_type="sample_submission", target_id=file_name[:64], detail=f"Sample submission audit failed before storage: {exc}")
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    saved_as = _saved_name(file_name)
    verdict = str(audit.get("verdict") or AUDIT_VERDICT_REVIEW)
    quarantined = verdict != AUDIT_VERDICT_PASS
    destination_root = QUARANTINE_DIR if quarantined else ACCEPTED_DIR
    destination = _safe_child_path(destination_root, saved_as)
    if not destination:
        raise HTTPException(status_code=400, detail="Invalid filename")
    destination.write_bytes(content)
    if quarantined:
        report = _build_report_payload(saved_as, file_name, len(content), _sha256(content), "quarantine", profile, audit)
        event_id = _sync_ids_event_from_report(db, request, report)
        _write_report(saved_as, report)
        _write_ids_log(db, current_user=current_user, action="ids_sample_submit_quarantine", target_type="sample_submission", target_id=saved_as, detail=f"{file_name} held in sandbox as {saved_as}; verdict={verdict}; risk={report.get('risk_level')}; event_id={event_id}")
        db.commit()
        event = db.query(IDSEvent).filter(IDSEvent.id == event_id).first()
        if event:
            auto_dispatch_notifications_for_event(
                db,
                serialize_notification_event(event),
                source="upload_quarantine",
            )
            db.commit()
        return {"ok": True, "filename": file_name, "saved_as": saved_as, "size": len(content), "url": None, "upload_state": "quarantined", "quarantined": True, "stored_in": "quarantine", "audit": report["audit"], "security_alert": {"style": "ids_quarantine", "http_status_hint": 403, "title": "样本送检未通过", "message": audit.get("summary"), "detail": f"样本已扣留到安全沙箱，编号 {saved_as}。"}}
    _write_ids_log(db, current_user=current_user, action="ids_sample_submit_release", target_type="sample_submission", target_id=saved_as, detail=f"{file_name} accepted into internal sample store as {saved_as}; risk={audit.get('risk_level')}; mode={audit.get('analysis_mode')}")
    db.commit()
    return {"ok": True, "filename": file_name, "saved_as": saved_as, "size": len(content), "url": None, "upload_state": "accepted", "quarantined": False, "stored_in": "accepted", "audit": audit}


@router.get("/quarantine")
def list_quarantine(request: Request, current_user: User = Depends(_admin)):
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    items: list[dict[str, Any]] = []
    total_bytes = 0
    daily_counts: dict[str, int] = defaultdict(int)
    ext_counts: dict[str, int] = defaultdict(int)
    latest_report: dict[str, Any] | None = None
    ai_quarantined_count = 0
    audit_hold_count = 0
    high_risk_count = 0
    medium_risk_count = 0
    for path in sorted(QUARANTINE_DIR.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        total_bytes += stat.st_size
        daily_counts[modified_at.strftime("%Y-%m-%d")] += 1
        report = _load_report(path.name)
        if report and (latest_report is None or _parse_iso(str(report.get("last_updated_at") or report.get("generated_at"))) > _parse_iso(str(latest_report.get("last_updated_at") or latest_report.get("generated_at")))):
            latest_report = report
        audit = _with_audit_compat(report.get("audit") if isinstance(report, dict) else {})
        risk_level = str((report or {}).get("risk_level") or audit.get("risk_level") or "medium")
        if risk_level == "high":
            high_risk_count += 1
        elif risk_level == "medium":
            medium_risk_count += 1
        if audit.get("llm_used"):
            ai_quarantined_count += 1
        if audit.get("verdict") == AUDIT_VERDICT_REVIEW:
            audit_hold_count += 1
        ext = str((report or {}).get("extension") or (path.suffix.lower() or "(none)"))
        ext_counts[ext] += 1
        items.append({"saved_as": path.name, "original_name": (report or {}).get("original_name") or (report or {}).get("file_name") or path.name, "file_name": (report or {}).get("file_name") or path.name, "size": stat.st_size, "modified_at": modified_at.isoformat(), "url": _quarantine_file_url(request, path.name), "risk_level": risk_level, "extension": ext, "has_report": bool(report), "report_generated_at": (report or {}).get("generated_at"), "report_risk_level": (report or {}).get("risk_level"), "audit_verdict": audit.get("verdict"), "report_verdict": audit.get("verdict"), "audit_confidence": audit.get("confidence"), "audit_summary": audit.get("summary")})
    labels, counts = [], []
    for days_ago in range(13, -1, -1):
        current_day = (today_start - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        labels.append(current_day[5:])
        counts.append(daily_counts.get(current_day, 0))
    today_count = sum(1 for item in items if str(item["modified_at"]).startswith(today_start.strftime("%Y-%m-%d")))
    week_count = sum(1 for item in items if datetime.fromisoformat(str(item["modified_at"]).replace("Z", "+00:00")) >= week_start)
    insights = ["当前安全沙箱为空，还没有待复核样本。"] if not items else [f"当前共有 {len(items)} 个样本保留在安全沙箱中，总空间占用 {_format_size(total_bytes)}。", f"高风险样本 {high_risk_count} 个，中风险样本 {medium_risk_count} 个。", f"近 7 天新增 {week_count} 个样本，其中 AI 参与审计 {ai_quarantined_count} 次。"]
    if items and audit_hold_count:
        insights.append(f"其中 {audit_hold_count} 个样本仍处于‘待复核’状态。")
    return {"items": items, "count": len(items), "analysis": {"total_bytes": total_bytes, "today_count": today_count, "week_count": week_count, "ai_quarantined_count": ai_quarantined_count, "audit_hold_count": audit_hold_count, "high_risk_count": high_risk_count, "medium_risk_count": medium_risk_count, "by_extension": [{"ext": ext, "count": count} for ext, count in sorted(ext_counts.items(), key=lambda item: (-item[1], item[0]))[:8]], "daily_labels": labels, "daily_counts": counts, "insights": insights, "generated_at": now.isoformat()}, "latest_report": latest_report}


@router.get("/quarantine/file/{filename:path}")
def get_quarantine_file(filename: str):
    path = _safe_child_path(QUARANTINE_DIR, filename)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Sandbox sample not found")
    return FileResponse(path, filename=path.name)


@router.get("/quarantine/{filename:path}/report")
def get_quarantine_report(filename: str, current_user: User = Depends(_admin)):
    report = _load_report(filename)
    if report:
        return report
    path = _safe_child_path(QUARANTINE_DIR, filename)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Sandbox report not found")
    content = path.read_bytes()
    try:
        profile, audit = _run_upload_audit(path.name, content)
    except UploadAIAuditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    report = _build_report_payload(path.name, path.name, len(content), _sha256(content), "quarantine", profile, audit)
    _write_report(path.name, report)
    return report


@router.post("/quarantine/analyze")
def analyze_quarantine(request: Request, payload: QuarantineAnalyzeRequest | None = Body(default=None), db: Session = Depends(get_db), current_user: User = Depends(_admin)):
    saved_as = ((payload.saved_as if payload else "") or "").strip()
    if not saved_as:
        names = [path.name for path in sorted(QUARANTINE_DIR.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True) if path.is_file()]
        if not names:
            return {"saved_as": "", "logs": [{"phase": "完成", "message": "当前没有待分析的沙箱样本。"}], "report": None}
        saved_as = names[0]
    path = _safe_child_path(QUARANTINE_DIR, saved_as)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Sandbox sample not found")
    content = path.read_bytes()
    try:
        profile, audit = _run_upload_audit(path.name, content)
    except UploadAIAuditError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    existing = _load_report(path.name)
    report = _build_report_payload(path.name, path.name, len(content), _sha256(content), "quarantine", profile, audit, existing=existing, sections=_build_report_sections(path.name, path.name, len(content), _sha256(content), "quarantine", profile, audit))
    existing_audit = existing.get("audit") if isinstance(existing, dict) and isinstance(existing.get("audit"), dict) else {}
    if existing_audit.get("linked_event_id"):
        report["audit"]["linked_event_id"] = existing_audit["linked_event_id"]
        if isinstance(report.get("decision_basis"), dict):
            report["decision_basis"]["linked_event_id"] = int(existing_audit["linked_event_id"])
    event_id = _sync_ids_event_from_report(db, request, report)
    if isinstance(report.get("decision_basis"), dict):
        report["decision_basis"]["linked_event_id"] = event_id
    _write_report(path.name, report)
    _write_ids_log(db, current_user=current_user, action="ids_sandbox_analyze", target_type="sandbox_file", target_id=path.name, detail=f"Analyzed sandbox sample {path.name}; verdict={audit.get('verdict')}; risk={report.get('risk_level')}; event_id={event_id}")
    db.commit()
    logs = [{"phase": "接收样本", "message": f"锁定沙箱样本 {path.name}，开始重新审计。"}, {"phase": "静态扫描", "message": f"完成静态特征提取，命中 {report.get('indicator_count', 0)} 个指标。"}, {"phase": "上传审计", "message": f"上传审计引擎返回 {audit.get('verdict')}，风险等级 {report.get('risk_level')}，置信度 {audit.get('confidence', 0)}。"}, {"phase": "处置决策", "message": "样本继续保留在安全沙箱中，报告已更新。"}, {"phase": "完成", "message": f"报告已落盘到 {_report_path(path.name).name if _report_path(path.name) else path.name}。"}]
    return {"saved_as": path.name, "logs": logs, "report": report}


@router.delete("/quarantine/{filename:path}")
def delete_quarantine_file(filename: str, db: Session = Depends(get_db), current_user: User = Depends(_admin)):
    path = _safe_child_path(QUARANTINE_DIR, filename)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Sandbox sample not found")
    report_path = _report_path(path.name)
    path.unlink()
    if report_path and report_path.exists():
        report_path.unlink()
    _write_ids_log(db, current_user=current_user, action="ids_sandbox_delete", target_type="sandbox_file", target_id=filename, detail=f"Deleted sandbox sample {filename}")
    db.commit()
    return {"ok": True}
