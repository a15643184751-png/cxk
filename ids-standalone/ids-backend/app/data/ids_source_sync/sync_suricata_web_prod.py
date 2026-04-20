from __future__ import annotations

import io
import json
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


UPSTREAM_ARCHIVE_URL = "http://rules.emergingthreats.net/open/suricata-7.0.3/emerging-all.rules.tar.gz"
RULE_FILE = Path(__file__).with_name("suricata-web-prod.rules")
MANIFEST_FILE = Path(__file__).with_name("suricata-web-prod.manifest.json")

# Curated application-layer rules pulled from the official ET Open bundle.
# We keep the exact upstream rule bodies and only constrain which SIDs/messages
# are bundled for this campus demo's request-side IDS runtime.
RULE_MATCH_SNIPPETS = [
    "Request to Hidden Environment File - Inbound",
    "Apache log4j RCE Attempt",
    "ClarkConnect Linux proxy.php XSS Attempt",
    "Hubscript XSS Attempt",
    "Possible APC Network Management Card Cross Site Scripting Attempt",
    "Possible bloofoxCMS 'search' Parameter Cross Site Scripting Attempt",
    "phpMyAdmin Remote Code Execution Proof of Concept (p=)",
    "phpMyAdmin Remote Code Execution Proof of Concept (c=)",
    "WEB-PHP phpinfo access",
    "ownCloud Information Disclosure Attempt (CVE-2023-49103)",
    "QNAP PhotoStation Pre-Auth Local File Disclosure Attempt",
    "QNAP Photo Station Path Traversal Attempt Inbound",
    "IBM Data Risk Manager Arbitrary File Download Attempt",
    "IBM Data Risk Manager Arbitrary File Download (CVE-2020-4430)",
    "Possible JBoss JMX Console Beanshell Deployer WAR Upload and Deployment Exploit Attempt",
    "JBoss jmx-console Access Control Bypass Attempt",
    "Possible CVE-2015-1427 Elastic Search Sandbox Escape Remote Code Execution Attempt",
    "Possible CVE-2014-3120 Elastic Search Remote Code Execution Attempt",
    "cmd powershell base64 encoded to Web Server",
    "Possible UNION SELECT SQL Injection In Cookie",
    "Possible SELECT FROM SQL Injection In Cookie",
    "Possible Citrix Gateway CVE-2023-24488 Exploit Attempt",
]


def _download_et_open_rules() -> str:
    with urllib.request.urlopen(UPSTREAM_ARCHIVE_URL, timeout=90) as resp:
        blob = resp.read()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        member = tf.extractfile("emerging-all.rules")
        if member is None:
            raise RuntimeError("emerging-all.rules not found in ET Open archive")
        return member.read().decode("utf-8", errors="ignore")


def _select_rules(text: str) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        normalized = raw_line.strip()
        if not normalized:
            continue
        if not any(snippet.lower() in normalized.lower() for snippet in RULE_MATCH_SNIPPETS):
            continue
        if normalized.startswith("#alert "):
            normalized = normalized[1:]
        if not normalized.startswith("alert "):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append(normalized)
    return selected


def _write_rules(rules: list[str]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = [
        "# Curated from the official ET Open Suricata bundle for campus IDS request screening.",
        f"# Upstream archive: {UPSTREAM_ARCHIVE_URL}",
        f"# Generated at: {timestamp}",
        f"# Rule count: {len(rules)}",
        "",
    ]
    RULE_FILE.write_text("\n".join([*header, *rules, ""]), encoding="utf-8")


def _write_manifest(rule_count: int) -> None:
    timestamp = datetime.now(timezone.utc)
    payload = {
        "source_key": "suricata-web-prod",
        "package_version": timestamp.strftime("%Y.%m.%d"),
        "release_timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trust_classification": "external_mature",
        "detector_family": "web",
        "provenance_note": "Curated from the official ET Open Suricata rules bundle for campus IDS request interception.",
        "upstream_archive_url": UPSTREAM_ARCHIVE_URL,
        "selection_strategy": "curated-message-match",
        "rule_count": rule_count,
        "artifact_path": "app/data/ids_source_sync/suricata-web-prod.rules",
    }
    MANIFEST_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    text = _download_et_open_rules()
    rules = _select_rules(text)
    if not rules:
        raise RuntimeError("No rules matched the configured ET Open selection list")
    _write_rules(rules)
    _write_manifest(len(rules))
    print(f"synced {len(rules)} ET Open rules into {RULE_FILE.name}")


if __name__ == "__main__":
    main()
