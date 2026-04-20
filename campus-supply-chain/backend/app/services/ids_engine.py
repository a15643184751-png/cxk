"""IDS 引擎：特征匹配、风险评分、攻击识别、Windows 防火墙封禁。"""
import re
import json
import subprocess
import platform
from urllib.parse import unquote, unquote_plus

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

CONTEXTUAL_SCORE_BOOSTS: list[tuple[str, str, int, str]] = [
    (r"(?i)\bsqlmap\b", "sql_injection", 24, "sqlmap_tooling"),
    (r"(?i)(union\s+select|sleep\s*\(|benchmark\s*\(|waitfor\s+delay|pg_sleep\s*\()", "sql_injection", 18, "high_impact_sqli_token"),
    (r"(?i)(<script[\s/>]|javascript:|onerror\s*=|onload\s*=|document\.cookie|alert\s*\()", "xss", 34, "active_script_xss"),
    (r"(?is)(<!DOCTYPE\s+[^\n>]+\s*\[[\s\S]{0,600}?<!ENTITY|file://|php://filter|expect://|gopher://|jar:)", "xxe", 34, "external_entity_resolution"),
    (r"(?i)(\.\./|\.\.\\|/etc/passwd|/etc/shadow|boot\.ini|win\.ini)", "path_traversal", 30, "sensitive_file_access"),
    (r"(?i)([;&|]\s*(whoami|id|cmd\.exe|powershell|curl|wget)|\bsystem\s*\(|\bpassthru\s*\(|\bshell_exec\s*\()", "cmd_injection", 30, "command_execution"),
    (r"(?i)(\$\{jndi:|jndi:(ldap|dns|rmi)://|\$\{lower:|\$\{env:)", "jndi_injection", 36, "jndi_lookup_chain"),
]

# 白名单路径（不检测）
WHITELIST_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/purchase/my",  # 教师「我的申请」接口，避免误拦
    "/api/upload",  # 匿名上传：由业务层返回 403 木马告警响应，避免 IDS 抢先阻断
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


def scan_request_detailed(method: str, path: str, query: str, body: str | bytes | None, headers: dict, user_agent: str) -> dict:
    """特征匹配 + 风险评分。"""
    path_decoded = _decode_request_fragment(path)
    query_decoded = _decode_request_fragment(query, plus_as_space=True)
    body_str = _extract_text(body)
    body_decoded = _decode_request_fragment(body_str, plus_as_space=True)
    ua = _extract_text(user_agent, 512)
    headers_str = " ".join(f"{k}:{v}" for k, v in (headers or {}).items())[:1024]

    combined = f"{method} {path_decoded} {query_decoded} {body_decoded} {ua} {headers_str}".lower()
    combined_raw = f"{path_decoded} {query_decoded} {body_decoded}"

    hits: list[dict] = []
    score = 0
    type_weight: dict[str, int] = {}
    for pattern, atype, weight in SIGNATURES:
        try:
            if re.search(pattern, combined, re.IGNORECASE | re.DOTALL) or re.search(pattern, combined_raw, re.IGNORECASE | re.DOTALL):
                hits.append({"attack_type": atype, "pattern": pattern[:96], "weight": weight})
                score += weight
                type_weight[atype] = type_weight.get(atype, 0) + weight
        except re.error:
            pass

    matched_types = {str(hit.get("attack_type") or "") for hit in hits}
    for pattern, atype, weight, label in CONTEXTUAL_SCORE_BOOSTS:
        if atype not in matched_types:
            continue
        try:
            if re.search(pattern, combined, re.IGNORECASE | re.DOTALL) or re.search(pattern, combined_raw, re.IGNORECASE | re.DOTALL):
                hits.append({"attack_type": atype, "pattern": f"context::{label}", "weight": weight})
                score += weight
                type_weight[atype] = type_weight.get(atype, 0) + weight
        except re.error:
            pass

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
        }
    attack_type = max(type_weight.items(), key=lambda x: x[1])[0]
    primary = next((h for h in hits if h["attack_type"] == attack_type), hits[0])
    confidence = min(95, 40 + len(hits) * 12 + (20 if score >= 70 else 0))
    return {
        "matched": True,
        "attack_type": attack_type,
        "signature_matched": str(primary["pattern"])[:128],
        "risk_score": score,
        "confidence": confidence,
        "hit_count": len(hits),
        "hits": hits,
        "detect_detail": json.dumps(hits, ensure_ascii=False)[:8000],
    }


def scan_request(method: str, path: str, query: str, body: str | bytes | None, headers: dict, user_agent: str) -> list[tuple[str, str]]:
    """兼容旧调用：返回 [(attack_type, signature_matched), ...]。"""
    detailed = scan_request_detailed(method, path, query, body, headers, user_agent)
    if not detailed.get("matched"):
        return []
    return [(detailed.get("attack_type", ""), detailed.get("signature_matched", ""))]


def block_ip_windows(ip: str) -> tuple[bool, str]:
    """调用 Windows 防火墙封禁 IP，返回 (成功, 消息)"""
    if platform.system() != "Windows":
        return False, "非 Windows 系统，跳过防火墙封禁"
    ip = ip.strip()
    if not ip or ip in ("127.0.0.1", "::1", "localhost"):
        return False, "不封禁本地地址"
    rule_name = f"IDS-Block-{ip.replace('.', '-').replace(':', '-')}"[:64]
    try:
        subprocess.run(
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
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
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
