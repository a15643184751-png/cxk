"""IDS 引擎：特征匹配、风险评分、攻击识别、Windows 防火墙封禁。"""
"""IDS detection engine for in-process request matching and firewall actions."""

import json
import logging
import platform
import re
import subprocess
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import unquote, unquote_plus

from ..database import SessionLocal
from ..models.ids_source_package import IDSSourcePackageActivation
from .ids_source_ops import SOURCE_DEMO_TEST, SOURCE_STATUS_DISABLED, SOURCE_TRANSITIONAL_LOCAL
from .ids_source_sync import SourceSyncValidationError, resolve_sync_path

# Transitional local matcher retained for continuity until mature-source
# integrations become the primary detector input.

logger = logging.getLogger("ids.runtime")
_RUNTIME_RULE_CACHE_TTL = timedelta(seconds=30)
_RUNTIME_RULE_CACHE_LOCK = Lock()
_RUNTIME_RULE_CACHE: dict[str, object] = {"loaded_at": None, "rules": []}

# 攻击特征库（正则）
SIGNATURES: list[tuple[str, str, int]] = [
    # SQL 注入（收紧 exec，避免匹配英文单词 execute）
    (
        r"(?i)(union\s+select|insert\s+into|drop\s+table|0x[0-9a-f]{4,}|'?\s*or\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+|benchmark\s*\(|sleep\s*\(|waitfor\s+delay|pg_sleep\s*\()",
        "sql_injection", 30,
    ),
    (r"(?i)(select\s+.{0,240}\s+from\s+|;?\s*--\s*$|/\*.{0,120}\*/|@@version|concat\s*\()", "sql_injection", 25),
    (r"(?i)(\bexec\s*\(|\bsp_executesql\b|\bxp_cmdshell\b)", "sql_injection", 30),
    # XSS
    (r"(?i)(<script[\s/>]|javascript:|onerror\s*=|onload\s*=|onclick\s*=|onmouseover\s*=|eval\s*\(|document\.cookie|alert\s*\()", "xss", 24),
    (r"(?i)(<iframe|<img\s+[^>]*onerror|vbscript:|expression\s*\()", "xss", 22),
    # XXE
    (r"(?is)(<!DOCTYPE\s+[^\n>]+\s*\[[\s\S]{0,600}?<!ENTITY\s+\w+\s+(SYSTEM|PUBLIC)\s+[\"'])", "xxe", 30),
    (r"(?i)(<!ENTITY\s+\w+\s+(SYSTEM|PUBLIC)\s+[\"']|file://|php://filter|expect://|gopher://|jar:)", "xxe", 28),
    # 路径遍历
    (r"\.\.(/|\\|%2f|%2F|%5c|%5C)", "path_traversal", 26),
    (r"(?i)(/etc/passwd|/etc/shadow|boot\.ini|win\.ini|c:\\windows\\system32\\config)", "path_traversal", 30),
    # 命令注入
    (r"(?i)[;&|]\s*(ls|cat|id|whoami|pwd|dir|cmd\.exe|powershell|wget|curl|nc\s|netcat)\b", "cmd_injection", 28),
    (r"(?i)(\$\s*\(|`[^`\n]{1,200}`|\bsystem\s*\(|\bpassthru\s*\(|\bshell_exec\s*\(|\bpopen\s*\()", "cmd_injection", 28),
    # JNDI / Log4Shell 类
    (r"(?i)(\$\{jndi:|jndi:(ldap|dns|rmi)://|\$\{lower:|\$\{env:)", "jndi_injection", 35),
    # 原型链污染常见 payload
    (r"(?i)(__proto__|constructor\s*\.\s*prototype|\[\"__proto__\"\])", "prototype_pollution", 22),
    # 常见扫描器/漏洞探测
    (r"(?i)(nikto|sqlmap|nmap|acunetix|nessus|\bburpsuite\b|w3af|masscan|zgrab)", "scanner", 16),
    (r"(?i)(/\.git/|/\.env\b|phpinfo\s*\(|wp-login\.php|wp-admin/setup|/administrator/|vendor/phpunit)", "scanner", 18),
    (r"(?i)(web\.config\b|\.htaccess\b|crossdomain\.xml|sftp-config\.json)", "scanner", 16),
    # 畸形请求
    (r"(?i)(\x00|\r\n\r\n\r\n)", "malformed", 14),
]

# 白名单路径（不检测）
WHITELIST_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/user/login",
    "/api/ids/events/ingest",
    "/api/ids/browser-route-probe",
    "/api/ids/frontend-route-probe",
    "/api/purchase/my",  # 教师「我的申请」接口，避免误拦
    "/api/upload",  # 内部样本送检接口：由送检审计流程自行处置，避免中间件重复抢先阻断
    "/",
    "/favicon.ico",
}

# 业务只读/库存接口：查询串可能被误判为 SQL 特征（如含 select/from），整段前缀放行
WHITELIST_PATH_PREFIXES = (
    "/api/stock/",  # 库存/出入库列表与查询
    "/api/goods",  # 物资列表（含 /api/goods）
    "/api/trace/",  # 溯源查询
)


def _extract_text(s: str | bytes | None, max_len: int = 2000) -> str:
    if s is None:
        return ""
    if isinstance(s, bytes):
        try:
            s = s.decode("utf-8", errors="replace")
        except Exception:
            s = repr(s)[:max_len]
    s = str(s)[:max_len]
    return s.replace("\x00", "")


def _decode_request_fragment(value: str | None, *, plus_as_space: bool = False) -> str:
    raw = value or ""
    try:
        return unquote_plus(raw) if plus_as_space else unquote(raw)
    except Exception:
        return raw


def refresh_runtime_rule_cache(force: bool = True) -> list[dict[str, object]]:
    now = datetime.utcnow()
    with _RUNTIME_RULE_CACHE_LOCK:
        cached_rules = list(_RUNTIME_RULE_CACHE.get("rules") or [])
        loaded_at = _RUNTIME_RULE_CACHE.get("loaded_at")
        if (
            not force
            and isinstance(loaded_at, datetime)
            and now - loaded_at < _RUNTIME_RULE_CACHE_TTL
        ):
            return cached_rules
        try:
            rules = _load_active_runtime_rules()
        except Exception as exc:
            logger.warning("Failed to refresh IDS runtime rule cache: %s", exc)
            _RUNTIME_RULE_CACHE["loaded_at"] = now
            return cached_rules
        _RUNTIME_RULE_CACHE["loaded_at"] = now
        _RUNTIME_RULE_CACHE["rules"] = rules
        return list(rules)


def _load_active_runtime_rules() -> list[dict[str, object]]:
    db = SessionLocal()
    try:
        activations = (
            db.query(IDSSourcePackageActivation)
            .order_by(IDSSourcePackageActivation.activated_at.desc(), IDSSourcePackageActivation.id.desc())
            .all()
        )
        latest_by_source: dict[int, IDSSourcePackageActivation] = {}
        for activation in activations:
            source_id = int(activation.source_id or 0)
            if source_id and source_id not in latest_by_source:
                latest_by_source[source_id] = activation

        runtime_rules: list[dict[str, object]] = []
        for activation in latest_by_source.values():
            source = activation.source
            intake = activation.package_intake
            if source is None or intake is None:
                continue
            if (source.trust_classification or "").strip() == SOURCE_DEMO_TEST:
                continue
            if (source.operational_status or "").strip() == SOURCE_STATUS_DISABLED:
                continue
            if (source.detector_family or "").strip() != "web":
                continue

            artifact_ref = (intake.artifact_path or "").strip()
            if not artifact_ref:
                continue
            try:
                artifact_path = resolve_sync_path(artifact_ref, kind="active rule artifact")
                artifact_bytes = artifact_path.read_bytes()
            except (OSError, SourceSyncValidationError) as exc:
                logger.warning(
                    "Skipping runtime load for IDS source %s: %s",
                    source.source_key or activation.source_id,
                    exc,
                )
                continue

            runtime_rules.extend(
                _extract_runtime_rules_from_artifact(
                    artifact_bytes=artifact_bytes,
                    source_key=source.source_key or "",
                    source_classification=(source.trust_classification or "").strip(),
                    detector_family=(source.detector_family or "").strip() or "web",
                    source_version=(activation.package_version or intake.package_version or "")[:64],
                )
            )
        return runtime_rules
    finally:
        db.close()


def _extract_runtime_rules_from_artifact(
    *,
    artifact_bytes: bytes,
    source_key: str,
    source_classification: str,
    detector_family: str,
    source_version: str,
) -> list[dict[str, object]]:
    runtime_rules: list[dict[str, object]] = []
    text = artifact_bytes.decode("utf-8", errors="ignore")
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//") or stripped.startswith(";"):
            continue
        runtime_rules.extend(
            _extract_runtime_rules_from_text_line(
                stripped,
                line_number=line_number,
                source_key=source_key,
                source_classification=source_classification,
                detector_family=detector_family,
                source_version=source_version,
            )
        )
    return runtime_rules


def _extract_runtime_rules_from_text_line(
    rule_text: str,
    *,
    line_number: int,
    source_key: str,
    source_classification: str,
    detector_family: str,
    source_version: str,
) -> list[dict[str, object]]:
    contents = [
        *_extract_suricata_option_values(rule_text, "content"),
        *_extract_suricata_option_values(rule_text, "uricontent"),
    ]
    if not contents:
        return []

    rule_name = _extract_suricata_option_value(rule_text, "msg") or f"{source_key}-rule-{line_number}"
    rule_id = _extract_suricata_numeric_value(rule_text, "sid") or f"line-{line_number}"
    attack_type = _infer_attack_type_from_runtime_rule(f"{rule_name} {rule_text}")
    weight = _runtime_rule_weight(attack_type)
    nocase = "nocase" in rule_text.lower()
    patterns = _normalize_runtime_patterns(contents)
    if not patterns:
        patterns = _derive_runtime_patterns(rule_text, rule_name)
    if not patterns:
        return []

    signature_preview = " && ".join(patterns[:3])[:96]
    return [
        {
            "attack_type": attack_type,
            "pattern": patterns[0][:256],
            "pattern_summary": signature_preview[:256],
            "patterns": patterns[:12],
            "signature_matched": f"{rule_id}:{signature_preview}"[:128],
            "weight": weight,
            "runtime_priority": 1,
            "nocase": nocase,
            "source_classification": source_classification[:32],
            "detector_family": detector_family[:32],
            "detector_name": source_key[:64],
            "source_rule_id": str(rule_id)[:128],
            "source_rule_name": str(rule_name)[:128],
            "source_version": source_version[:64],
            "source_freshness": "current",
        }
    ]


def _extract_suricata_option_value(rule_text: str, option_name: str) -> str:
    match = re.search(rf"\b{re.escape(option_name)}\b\s*:\s*\"((?:\\.|[^\"\\])*)\"", rule_text)
    return match.group(1) if match else ""


def _extract_suricata_option_values(rule_text: str, option_name: str) -> list[str]:
    return re.findall(rf"\b{re.escape(option_name)}\b\s*:\s*\"((?:\\.|[^\"\\])*)\"", rule_text)


def _extract_suricata_numeric_value(rule_text: str, option_name: str) -> str:
    match = re.search(rf"\b{re.escape(option_name)}\b\s*:\s*([0-9]+)", rule_text)
    return match.group(1) if match else ""


def _normalize_runtime_patterns(contents: list[str]) -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    for content in contents:
        decoded = _unescape_suricata_string(content).strip()
        if not decoded:
            continue
        if _looks_generic_runtime_token(decoded):
            continue
        dedupe_key = decoded.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        patterns.append(decoded[:256])
    return patterns


def _looks_generic_runtime_token(value: str) -> bool:
    token = (value or "").strip()
    lowered = token.lower()
    if not token:
        return True
    if lowered in {
        "get",
        "post",
        "head",
        "put",
        "patch",
        "delete",
        "options",
        "trace",
        "connect",
        ":",
        "${",
        "%7b",
        "%24%7b",
        "cookie:",
        "cookie",
        "host:",
        "user-agent:",
        "://",
        "http://",
        "https://",
    }:
        return True
    if len(token) < 3 and token not in {"..", "../", "./"}:
        return True
    if not any(ch.isalnum() for ch in token) and token not in {"..", "../", "./"}:
        return True
    return False


def _derive_runtime_patterns(rule_text: str, rule_name: str) -> list[str]:
    lowered = f"{rule_name} {rule_text}".lower()
    if "log4j" in lowered or "jndi" in lowered:
        derived: list[str] = []
        for token in (
            "${jndi:",
            "${env:",
            "%7bjndi%3a",
            "${lower:j",
            "${upper:j",
            ":-j}${",
            "/tomcatbypass/command/base64/",
            "aws_access_key_id",
        ):
            if token in lowered and token not in derived:
                derived.append(token)
        return derived
    return []


def _unescape_suricata_string(value: str) -> str:
    text = value.replace(r"\\", "\\").replace(r"\"", "\"")
    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] != "|":
            parts.append(text[cursor])
            cursor += 1
            continue
        end = text.find("|", cursor + 1)
        if end < 0:
            parts.append(text[cursor])
            cursor += 1
            continue
        hex_block = text[cursor + 1 : end].strip()
        decoded = bytearray()
        valid_block = True
        for piece in hex_block.split():
            if not piece:
                continue
            try:
                decoded.append(int(piece, 16))
            except ValueError:
                valid_block = False
                break
        if valid_block and decoded:
            parts.append(decoded.decode("utf-8", errors="ignore"))
        else:
            parts.append(f"|{hex_block}|")
        cursor = end + 1
    return "".join(parts)


def _infer_attack_type_from_runtime_rule(rule_text: str) -> str:
    lowered = (rule_text or "").lower()
    if "log4j" in lowered or "jndi" in lowered:
        return "jndi_injection"
    if "sql" in lowered or "sqli" in lowered:
        return "sql_injection"
    if "cmd" in lowered or "powershell" in lowered or "command injection" in lowered or "remote code execution" in lowered or "runtime.getruntime().exec" in lowered:
        return "cmd_injection"
    if "xss" in lowered or "<script" in lowered:
        return "xss"
    if "xxe" in lowered or "<!doctype" in lowered or "<!entity" in lowered or "xml external entity" in lowered:
        return "xxe"
    if "traversal" in lowered or "../" in lowered or "file disclosure" in lowered or "local file inclusion" in lowered or "file download" in lowered:
        return "path_traversal"
    if "webshell" in lowered or "<?php" in lowered or "shell" in lowered:
        return "malware"
    if ".env" in lowered or "phpinfo" in lowered or "probe" in lowered or "exposed" in lowered:
        return "scanner"
    if "probe" in lowered or "scan" in lowered or "scanner" in lowered:
        return "scanner"
    return "malformed"


def _runtime_rule_weight(attack_type: str) -> int:
    return {
        "sql_injection": 82,
        "xss": 76,
        "xxe": 80,
        "path_traversal": 78,
        "cmd_injection": 86,
        "scanner": 72,
        "malware": 88,
        "prototype_pollution": 76,
        "jndi_injection": 92,
        "malformed": 70,
    }.get((attack_type or "").strip(), 72)


def _runtime_rule_matches(
    rule: dict[str, object],
    *,
    combined_text: str,
    combined_lower: str,
    combined_raw: str,
    combined_raw_lower: str,
) -> str:
    patterns = [str(item).strip() for item in (rule.get("patterns") or []) if str(item).strip()]
    if not patterns:
        patterns = [str(rule.get("pattern") or "").strip()]
    if not patterns:
        return ""
    matched_tokens: list[str] = []
    nocase = bool(rule.get("nocase"))
    for pattern in patterns:
        if nocase:
            needle = pattern.lower()
            if needle not in combined_lower and needle not in combined_raw_lower:
                return ""
        else:
            if pattern not in combined_text and pattern not in combined_raw:
                return ""
        matched_tokens.append(pattern[:128])
    return " && ".join(matched_tokens[:3])[:512]


def scan_request_detailed(method: str, path: str, query: str, body: str | bytes | None, headers: dict, user_agent: str) -> dict:
    """特征匹配 + 风险评分。"""
    path_decoded = _decode_request_fragment(path)
    query_decoded = _decode_request_fragment(query, plus_as_space=True)
    body_str = _extract_text(body)
    body_decoded = _decode_request_fragment(body_str, plus_as_space=True)
    ua = _extract_text(user_agent, 512)
    headers_str = " ".join(f"{k}:{v}" for k, v in (headers or {}).items())[:1024]

    request_target = path_decoded or "/"
    if query_decoded:
        request_target = f"{request_target}?{query_decoded}"

    combined_text = f"{method} {request_target} {query_decoded} {body_decoded} {ua} {headers_str}"
    combined_raw = f"{request_target} {query_decoded} {body_decoded}"
    combined_lower = combined_text.lower()
    combined_raw_lower = combined_raw.lower()

    hits: list[dict] = []
    score = 0
    type_weight: dict[str, int] = {}
    runtime_rules = refresh_runtime_rule_cache(force=False)
    rule_source_mode = "external_runtime" if runtime_rules else "legacy_local"

    for runtime_rule in runtime_rules:
        try:
            matched_value = _runtime_rule_matches(
                runtime_rule,
                combined_text=combined_text,
                combined_lower=combined_lower,
                combined_raw=combined_raw,
                combined_raw_lower=combined_raw_lower,
            )
            if not matched_value:
                continue
            attack_type = str(runtime_rule.get("attack_type") or "scanner")
            weight = int(runtime_rule.get("weight") or 0)
            hits.append(
                {
                    "attack_type": attack_type,
                    "pattern": str(runtime_rule.get("pattern_summary") or runtime_rule.get("pattern") or "")[:96],
                    "signature_matched": str(runtime_rule.get("signature_matched") or "")[:128],
                    "weight": weight,
                    "runtime_priority": int(runtime_rule.get("runtime_priority") or 1),
                    "matched_part": "request",
                    "matched_value": matched_value,
                    "source_classification": str(runtime_rule.get("source_classification") or "")[:32],
                    "detector_family": str(runtime_rule.get("detector_family") or "")[:32],
                    "detector_name": str(runtime_rule.get("detector_name") or "")[:64],
                    "source_rule_id": str(runtime_rule.get("source_rule_id") or "")[:128],
                    "source_rule_name": str(runtime_rule.get("source_rule_name") or "")[:128],
                    "source_version": str(runtime_rule.get("source_version") or "")[:64],
                    "source_freshness": str(runtime_rule.get("source_freshness") or "current")[:16],
                }
            )
            score += weight
            type_weight[attack_type] = type_weight.get(attack_type, 0) + weight
        except Exception as exc:
            logger.warning("Skipping invalid runtime IDS rule during scan: %s", exc)

    if not hits:
        for index, (pattern, atype, weight) in enumerate(SIGNATURES, start=1):
            try:
                if re.search(pattern, combined_text, re.IGNORECASE | re.DOTALL) or re.search(
                    pattern,
                    combined_raw,
                    re.IGNORECASE | re.DOTALL,
                ):
                    hits.append(
                        {
                            "attack_type": atype,
                            "pattern": pattern[:96],
                            "signature_matched": pattern[:128],
                            "weight": weight,
                            "runtime_priority": 0,
                            "source_classification": SOURCE_TRANSITIONAL_LOCAL,
                            "detector_family": "web",
                            "detector_name": "legacy_inline_signatures",
                            "source_rule_id": f"legacy::{atype}::{index}"[:128],
                            "source_rule_name": f"legacy_{atype}"[:128],
                            "source_version": "legacy-inline",
                            "source_freshness": "current",
                        }
                    )
                    score += weight
                    type_weight[atype] = type_weight.get(atype, 0) + weight
            except re.error:
                continue
    score = min(score, 100)
    if not hits:
        return {
            "matched": False,
            "attack_type": "",
            "signature_matched": "",
            "risk_score": 0,
            "confidence": 0,
            "hit_count": 0,
            "hits": [],
            "detect_detail": "[]",
            "rule_source_mode": rule_source_mode,
        }
    attack_type = max(type_weight.items(), key=lambda x: x[1])[0]
    primary_candidates = [hit for hit in hits if hit["attack_type"] == attack_type]
    primary = max(
        primary_candidates or hits,
        key=lambda hit: (
            int(hit.get("weight") or 0),
            int(hit.get("runtime_priority") or 0),
            len(str(hit.get("signature_matched") or "")),
        ),
    )
    confidence = min(95, 40 + len(hits) * 12 + (20 if score >= 70 else 0))
    return {
        "matched": True,
        "attack_type": attack_type,
        "signature_matched": str(primary.get("signature_matched") or primary.get("pattern") or "")[:128],
        "risk_score": score,
        "confidence": confidence,
        "hit_count": len(hits),
        "hits": hits,
        "detect_detail": json.dumps(hits, ensure_ascii=False)[:8000],
        "source_classification": str(primary.get("source_classification") or "")[:32],
        "detector_family": str(primary.get("detector_family") or "")[:32],
        "detector_name": str(primary.get("detector_name") or "")[:64],
        "source_rule_id": str(primary.get("source_rule_id") or "")[:128],
        "source_rule_name": str(primary.get("source_rule_name") or "")[:128],
        "source_version": str(primary.get("source_version") or "")[:64],
        "source_freshness": str(primary.get("source_freshness") or "current")[:16],
        "rule_source_mode": rule_source_mode,
    }


def scan_request(method: str, path: str, query: str, body: str | bytes | None, headers: dict, user_agent: str) -> list[tuple[str, str]]:
    """兼容旧调用：返回 [(attack_type, signature_matched), ...]。"""
    detailed = scan_request_detailed(method, path, query, body, headers, user_agent)
    if not detailed.get("matched"):
        return []
    return [(detailed.get("attack_type", ""), detailed.get("signature_matched", ""))]


def scan_frontend_route_probe(path: str, query: str, user_agent: str = "") -> dict:
    """Inspect browser-only route probes that never traverse the backend middleware."""
    detailed = scan_request_detailed("GET", path, query, "", {"x-frontend-route-guard": "1"}, user_agent)
    if detailed.get("matched"):
        boosted = dict(detailed)
        if int(boosted.get("risk_score") or 0) < 82:
            boosted["risk_score"] = 82
        return boosted

    path_decoded = _decode_request_fragment(path)
    query_decoded = _decode_request_fragment(query, plus_as_space=True)
    request_target = path_decoded or "/"
    if query_decoded:
        request_target = f"{request_target}?{query_decoded}"
    combined_text = f"GET {request_target} {query_decoded} {_extract_text(user_agent, 512)}"
    combined_raw = f"{request_target} {query_decoded}"

    hits: list[dict[str, object]] = []
    score = 0
    type_weight: dict[str, int] = {}

    for index, (pattern, atype, weight) in enumerate(SIGNATURES, start=1):
        try:
            if re.search(pattern, combined_text, re.IGNORECASE | re.DOTALL) or re.search(
                pattern,
                combined_raw,
                re.IGNORECASE | re.DOTALL,
            ):
                boosted_weight = max(
                    int(weight),
                    82 if atype in {"xss", "xxe", "jndi_injection", "sql_injection", "path_traversal", "cmd_injection", "malware"} else 72,
                )
                hits.append(
                    {
                        "attack_type": atype,
                        "pattern": pattern[:96],
                        "signature_matched": pattern[:128],
                        "weight": boosted_weight,
                        "runtime_priority": 0,
                        "source_classification": SOURCE_TRANSITIONAL_LOCAL,
                        "detector_family": "web_ui_guard",
                        "detector_name": "frontend_route_guard",
                        "source_rule_id": f"frontend-route::{atype}::{index}"[:128],
                        "source_rule_name": f"frontend_route_{atype}"[:128],
                        "source_version": "browser-route-guard",
                        "source_freshness": "current",
                    }
                )
                score += boosted_weight
                type_weight[atype] = type_weight.get(atype, 0) + boosted_weight
        except re.error:
            continue

    if not hits:
        return {
            "matched": False,
            "attack_type": "",
            "signature_matched": "",
            "risk_score": 0,
            "confidence": 0,
            "hit_count": 0,
            "hits": [],
            "detect_detail": "[]",
            "rule_source_mode": "frontend_route_guard",
        }

    score = min(score, 100)
    attack_type = max(type_weight.items(), key=lambda item: item[1])[0]
    primary_candidates = [hit for hit in hits if hit["attack_type"] == attack_type]
    primary = max(
        primary_candidates or hits,
        key=lambda hit: (
            int(hit.get("weight") or 0),
            int(hit.get("runtime_priority") or 0),
            len(str(hit.get("signature_matched") or "")),
        ),
    )
    confidence = min(97, 58 + len(hits) * 10)
    return {
        "matched": True,
        "attack_type": attack_type,
        "signature_matched": str(primary.get("signature_matched") or primary.get("pattern") or "")[:128],
        "risk_score": score,
        "confidence": confidence,
        "hit_count": len(hits),
        "hits": hits,
        "detect_detail": json.dumps(hits, ensure_ascii=False)[:8000],
        "source_classification": str(primary.get("source_classification") or "")[:32],
        "detector_family": str(primary.get("detector_family") or "")[:32],
        "detector_name": str(primary.get("detector_name") or "")[:64],
        "source_rule_id": str(primary.get("source_rule_id") or "")[:128],
        "source_rule_name": str(primary.get("source_rule_name") or "")[:128],
        "source_version": str(primary.get("source_version") or "")[:64],
        "source_freshness": str(primary.get("source_freshness") or "current")[:16],
        "rule_source_mode": "frontend_route_guard",
    }


def block_ip_windows(ip: str) -> tuple[bool, str]:
    """调用 Windows 防火墙封禁 IP，返回 (成功, 消息)"""
    if platform.system() != "Windows":
        return False, "非 Windows 系统，跳过防火墙封禁"
    ip = ip.strip()
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return False, "不封禁本地地址"
    rule_name = f"IDS-Block-{ip.replace('.', '-').replace(':', '-')}"[:64]
    try:
        completed = subprocess.run(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}",
                "dir=in",
                "action=block",
                f"remoteip={ip}",
                "protocol=any",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if detail:
                return False, f"netsh add rule failed: {detail[:240]}"
            return False, f"netsh add rule failed with exit code {completed.returncode}"
        return True, rule_name
    except subprocess.TimeoutExpired:
        return False, "netsh 执行超时"
    except Exception as e:
        return False, str(e)


def unblock_ip_windows(ip: str) -> tuple[bool, str]:
    """调用 Windows 防火墙解封 IP，返回 (成功, 消息)。"""
    if platform.system() != "Windows":
        return False, "非 Windows 系统，跳过防火墙解封"
    ip = ip.strip()
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return False, "不解封本地地址"
    rule_name = f"IDS-Block-{ip.replace('.', '-').replace(':', '-')}"[:64]
    try:
        completed = subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if detail:
                return False, f"netsh delete rule failed: {detail[:240]}"
            return False, f"netsh delete rule failed with exit code {completed.returncode}"
        return True, rule_name
    except subprocess.TimeoutExpired:
        return False, "netsh 执行超时"
    except Exception as e:
        return False, str(e)


def is_whitelisted(path: str) -> bool:
    if not path:
        return False
    raw = path.split("?")[0]
    p = raw.rstrip("/") or "/"
    if p in WHITELIST_PATHS:
        return True
    if any(p.startswith(w.replace("*", "")) for w in WHITELIST_PATHS if "*" in w):
        return True
    for prefix in WHITELIST_PATH_PREFIXES:
        if raw == prefix.rstrip("/") or raw.startswith(prefix):
            return True
    return False
