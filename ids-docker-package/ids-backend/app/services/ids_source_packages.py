from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.ids_source import IDSSource
from ..models.ids_source_package import IDSSourcePackageActivation, IDSSourcePackageIntake

PACKAGE_RESULT_PREVIEWED = "previewed"
PACKAGE_RESULT_ACTIVATED = "activated"
PACKAGE_RESULT_REJECTED = "rejected"
PACKAGE_RESULT_FAILED = "failed"

VERSION_STATE_NEWER = "newer"
VERSION_STATE_UNCHANGED = "unchanged"
VERSION_STATE_OLDER = "older"
VERSION_STATE_CONFLICTING = "conflicting"


def normalize_package_version(value: str) -> str:
    return (value or "").strip()[:64]


def compare_package_versions(candidate_version: str, active_version: str | None) -> str:
    candidate = normalize_package_version(candidate_version)
    active = normalize_package_version(active_version or "")
    if not active:
        return VERSION_STATE_NEWER
    if candidate == active:
        return VERSION_STATE_UNCHANGED

    candidate_parts = _tokenize_version(candidate)
    active_parts = _tokenize_version(active)
    if candidate_parts and active_parts:
        if candidate_parts > active_parts:
            return VERSION_STATE_NEWER
        if candidate_parts < active_parts:
            return VERSION_STATE_OLDER
    return VERSION_STATE_CONFLICTING


def list_recent_package_intakes(
    db: Session,
    source_ids: list[int],
    *,
    limit_per_source: int = 3,
) -> dict[int, list[IDSSourcePackageIntake]]:
    ids = [source_id for source_id in source_ids if source_id]
    if not ids:
        return {}
    rows = (
        db.query(IDSSourcePackageIntake)
        .filter(IDSSourcePackageIntake.source_id.in_(ids))
        .order_by(IDSSourcePackageIntake.created_at.desc(), IDSSourcePackageIntake.id.desc())
        .all()
    )
    grouped: dict[int, list[IDSSourcePackageIntake]] = {}
    for row in rows:
        bucket = grouped.setdefault(int(row.source_id), [])
        if len(bucket) < limit_per_source:
            bucket.append(row)
    return grouped


def list_latest_package_activations(
    db: Session,
    source_ids: list[int],
) -> dict[int, IDSSourcePackageActivation]:
    ids = [source_id for source_id in source_ids if source_id]
    if not ids:
        return {}
    rows = (
        db.query(IDSSourcePackageActivation)
        .filter(IDSSourcePackageActivation.source_id.in_(ids))
        .order_by(IDSSourcePackageActivation.activated_at.desc(), IDSSourcePackageActivation.id.desc())
        .all()
    )
    latest: dict[int, IDSSourcePackageActivation] = {}
    for row in rows:
        source_id = int(row.source_id)
        if source_id not in latest:
            latest[source_id] = row
    return latest


def list_recent_package_activations(
    db: Session,
    source_ids: list[int],
    *,
    limit_per_source: int = 3,
) -> dict[int, list[IDSSourcePackageActivation]]:
    # History queries stay intentionally small because the security-center
    # package view is reviewer-facing, not a raw export surface.
    ids = [source_id for source_id in source_ids if source_id]
    if not ids:
        return {}
    rows = (
        db.query(IDSSourcePackageActivation)
        .filter(IDSSourcePackageActivation.source_id.in_(ids))
        .order_by(IDSSourcePackageActivation.activated_at.desc(), IDSSourcePackageActivation.id.desc())
        .all()
    )
    grouped: dict[int, list[IDSSourcePackageActivation]] = {}
    for row in rows:
        bucket = grouped.setdefault(int(row.source_id), [])
        if len(bucket) < limit_per_source:
            bucket.append(row)
    return grouped


def build_package_preview_summary(
    source: IDSSource,
    *,
    package_version: str,
    release_timestamp: datetime | None = None,
    provenance_note: str = "",
    active_activation: IDSSourcePackageActivation | None = None,
    artifact_path: str = "",
    artifact_sha256: str = "",
    artifact_size_bytes: int | None = None,
    rule_count: int | None = None,
) -> dict:
    changed_fields: list[str] = []
    active_version = active_activation.package_version if active_activation else ""
    version_change_state = compare_package_versions(package_version, active_version)
    if package_version and package_version != active_version:
        changed_fields.append("package_version")
    if release_timestamp:
        changed_fields.append("release_timestamp")
    if provenance_note and provenance_note.strip() != (source.provenance_note or "").strip():
        changed_fields.append("provenance_note")
    if artifact_path:
        changed_fields.append("artifact_path")
    if artifact_sha256:
        changed_fields.append("artifact_sha256")
    if artifact_size_bytes:
        changed_fields.append("artifact_size_bytes")
    if rule_count is not None:
        changed_fields.append("rule_count")
    return {
        "source_id": source.id,
        "source_key": source.source_key or "",
        "package_version": normalize_package_version(package_version),
        "version_change_state": version_change_state,
        "changed_fields": changed_fields,
        "visible_warning": _build_version_warning(version_change_state),
        "artifact_path": artifact_path[:255],
        "artifact_sha256": artifact_sha256[:64],
        "artifact_size_bytes": int(artifact_size_bytes or 0),
        "rule_count": int(rule_count or 0),
    }


def _tokenize_version(value: str) -> tuple:
    parts = re.split(r"[^0-9A-Za-z]+", value)
    tokens: list[tuple[int, object]] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            tokens.append((0, int(part)))
        else:
            tokens.append((1, part.lower()))
    return tuple(tokens)


def _build_version_warning(version_change_state: str) -> str:
    if version_change_state == VERSION_STATE_OLDER:
        return "Previewed package version is older than the current active version."
    if version_change_state == VERSION_STATE_CONFLICTING:
        return "Previewed package version cannot be compared cleanly with the active version."
    return ""
