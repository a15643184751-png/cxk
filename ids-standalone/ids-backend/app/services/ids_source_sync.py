from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ..models.ids_source import IDSSource
from .ids_source_ops import normalize_source_key

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_SYNC_ROOTS = (BACKEND_ROOT, REPO_ROOT)


class SourceSyncValidationError(ValueError):
    pass


def load_source_sync_payload(source: IDSSource) -> dict[str, object]:
    sync_endpoint = (source.sync_endpoint or "").strip()
    if not sync_endpoint:
        raise SourceSyncValidationError("sync_endpoint is required before this source can be synchronized.")

    manifest_path = resolve_sync_path(sync_endpoint, kind="sync manifest")
    manifest = _load_sync_manifest(manifest_path)

    manifest_source_key = normalize_source_key(str(manifest.get("source_key") or ""))
    source_key = normalize_source_key(source.source_key or "")
    if manifest_source_key and manifest_source_key != source_key:
        raise SourceSyncValidationError(
            f"Manifest source_key mismatch: expected {source_key}, got {manifest_source_key}."
        )

    package_version = str(manifest.get("package_version") or "").strip()[:64]
    if not package_version:
        raise SourceSyncValidationError("Manifest package_version is required.")

    manifest_trust = str(manifest.get("trust_classification") or source.trust_classification or "").strip()
    if manifest_trust and manifest_trust != (source.trust_classification or "").strip():
        raise SourceSyncValidationError(
            f"Manifest trust_classification mismatch: expected {source.trust_classification}, got {manifest_trust}."
        )

    manifest_family = str(manifest.get("detector_family") or source.detector_family or "").strip()[:32]
    if manifest_family and manifest_family != (source.detector_family or "").strip():
        raise SourceSyncValidationError(
            f"Manifest detector_family mismatch: expected {source.detector_family}, got {manifest_family}."
        )

    artifact_ref = str(manifest.get("artifact_path") or "").strip()
    if not artifact_ref:
        raise SourceSyncValidationError("Manifest artifact_path is required.")

    artifact_path = resolve_sync_path(artifact_ref, kind="rule artifact", base_dir=manifest_path.parent)
    artifact_bytes = artifact_path.read_bytes()
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    artifact_size_bytes = len(artifact_bytes)
    rule_count = count_rules_from_artifact(artifact_path, artifact_bytes)
    provenance_note = str(manifest.get("provenance_note") or source.provenance_note or "").strip()[:2000]
    release_timestamp = parse_release_timestamp(manifest.get("release_timestamp"))

    return {
        "source_key": source_key,
        "package_version": package_version,
        "trust_classification": manifest_trust or (source.trust_classification or "").strip(),
        "detector_family": manifest_family or (source.detector_family or "").strip(),
        "provenance_note": provenance_note,
        "release_timestamp": release_timestamp,
        "manifest_path": display_sync_path(manifest_path),
        "artifact_path": display_sync_path(artifact_path),
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": artifact_size_bytes,
        "rule_count": rule_count,
        "sync_detail": build_sync_detail(
            package_version=package_version,
            manifest_path=display_sync_path(manifest_path),
            artifact_path=display_sync_path(artifact_path),
            artifact_sha256=artifact_sha256,
            artifact_size_bytes=artifact_size_bytes,
            rule_count=rule_count,
        ),
    }


def resolve_sync_path(value: str, *, kind: str, base_dir: Path | None = None) -> Path:
    raw = Path(value)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        if base_dir is not None:
            candidates.append(base_dir / raw)
        candidates.append(BACKEND_ROOT / raw)
        candidates.append(REPO_ROOT / raw)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if not is_path_within_allowed_roots(resolved):
            continue
        if resolved.exists() and resolved.is_file():
            return resolved

    raise SourceSyncValidationError(f"{kind} not found or outside the repository: {value}")


def is_path_within_allowed_roots(path: Path) -> bool:
    for root in ALLOWED_SYNC_ROOTS:
        try:
            path.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _load_sync_manifest(manifest_path: Path) -> dict[str, object]:
    if manifest_path.suffix.lower() != ".json":
        raise SourceSyncValidationError("sync manifest must be a JSON file.")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceSyncValidationError(f"sync manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceSyncValidationError(f"sync manifest is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceSyncValidationError("sync manifest must contain a top-level JSON object.")
    return payload


def parse_release_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise SourceSyncValidationError("release_timestamp must be an ISO-8601 string.")

    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SourceSyncValidationError("release_timestamp must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def count_rules_from_artifact(artifact_path: Path, artifact_bytes: bytes) -> int:
    if artifact_path.suffix.lower() == ".json":
        try:
            payload = json.loads(artifact_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            rules = payload.get("rules")
            if isinstance(rules, list):
                return len(rules)

    text = artifact_bytes.decode("utf-8", errors="ignore")
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith(";"):
            continue
        count += 1
    return count


def display_sync_path(path: Path) -> str:
    for root in (REPO_ROOT, BACKEND_ROOT):
        try:
            return path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return path.resolve().as_posix()


def build_sync_detail(
    *,
    package_version: str,
    manifest_path: str,
    artifact_path: str,
    artifact_sha256: str,
    artifact_size_bytes: int,
    rule_count: int,
) -> str:
    return (
        f"Imported package {package_version} from {manifest_path}; "
        f"artifact={artifact_path}; rules={rule_count}; "
        f"size_bytes={artifact_size_bytes}; sha256={artifact_sha256[:16]}..."
    )[:1000]
