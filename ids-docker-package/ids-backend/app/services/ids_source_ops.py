from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.ids_event import IDSEvent
from ..models.ids_source import IDSSource, IDSSourceSyncAttempt

SOURCE_EXTERNAL_MATURE = "external_mature"
SOURCE_CUSTOM_PROJECT = "custom_project"
SOURCE_TRANSITIONAL_LOCAL = "transitional_local"
SOURCE_DEMO_TEST = "demo_test"

SOURCE_STATUS_ENABLED = "enabled"
SOURCE_STATUS_DISABLED = "disabled"
SOURCE_STATUS_FAILING = "failing"
SOURCE_STATUS_DRAFT = "draft"

SYNC_MODE_MANUAL = "manual"
SYNC_MODE_SCHEDULED = "scheduled"
SYNC_MODE_NOT_APPLICABLE = "not_applicable"

SYNC_STATUS_SUCCESS = "success"
SYNC_STATUS_FAILED = "failed"
SYNC_STATUS_SKIPPED = "skipped"
SYNC_STATUS_NEVER = "never_synced"

HEALTH_HEALTHY = "healthy"
HEALTH_STALE = "stale"
HEALTH_DISABLED = "disabled"
HEALTH_FAILING = "failing"
HEALTH_NEVER = "never_synced"

SOURCE_ACTIVITY_LOOKBACK_DAYS = 7

TRUST_CLASSIFICATIONS = {
    SOURCE_EXTERNAL_MATURE,
    SOURCE_CUSTOM_PROJECT,
    SOURCE_TRANSITIONAL_LOCAL,
    SOURCE_DEMO_TEST,
}
OPERATIONAL_STATUSES = {
    SOURCE_STATUS_ENABLED,
    SOURCE_STATUS_DISABLED,
    SOURCE_STATUS_FAILING,
    SOURCE_STATUS_DRAFT,
}
SYNC_MODES = {
    SYNC_MODE_MANUAL,
    SYNC_MODE_SCHEDULED,
    SYNC_MODE_NOT_APPLICABLE,
}


def normalize_source_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", (value or "").strip().lower()).strip("-")
    return normalized[:128]


def is_trusted_production_source(source: IDSSource) -> bool:
    return (source.trust_classification or "").strip() != SOURCE_DEMO_TEST


def derive_source_health_state(source: IDSSource, *, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    status = (source.operational_status or "").strip()
    last_status = (source.last_sync_status or "").strip()
    freshness_target_hours = max(int(source.freshness_target_hours or 0), 0)
    last_synced_at = source.last_synced_at

    if status == SOURCE_STATUS_DISABLED:
        return HEALTH_DISABLED
    if status == SOURCE_STATUS_FAILING or last_status == SYNC_STATUS_FAILED:
        return HEALTH_FAILING
    if not last_synced_at:
        return HEALTH_NEVER
    if freshness_target_hours and last_synced_at < now - timedelta(hours=freshness_target_hours):
        return HEALTH_STALE
    return HEALTH_HEALTHY


def build_source_warning(source: IDSSource, *, health_state: str, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    if health_state == HEALTH_DISABLED:
        return "Source is disabled and excluded from active sync operations."
    if health_state == HEALTH_FAILING:
        return (source.last_sync_detail or "Latest sync attempt failed.").strip()
    if not is_trusted_production_source(source):
        return "Demo/test source remains visible but does not count as trusted production coverage."
    if health_state == HEALTH_NEVER:
        return "Source has not completed a successful sync yet."
    if health_state == HEALTH_STALE:
        if source.last_synced_at and source.freshness_target_hours:
            age_hours = max(int((now - source.last_synced_at).total_seconds() // 3600), 0)
            return f"Last successful sync is {age_hours}h old, beyond the {int(source.freshness_target_hours)}h target."
        return "Source freshness is outside the configured target."
    return ""


def list_recent_source_activity(
    db: Session,
    source_keys: list[str],
    *,
    lookback_days: int = SOURCE_ACTIVITY_LOOKBACK_DAYS,
) -> dict[str, dict[str, object]]:
    keys = [key for key in source_keys if key]
    if not keys:
        return {}
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    rows = (
        db.query(
            IDSEvent.detector_name.label("source_key"),
            func.count(IDSEvent.id).label("recent_incident_count"),
            func.max(IDSEvent.created_at).label("recent_incident_last_seen_at"),
        )
        .filter(IDSEvent.detector_name.in_(keys))
        .filter(IDSEvent.created_at >= cutoff)
        .group_by(IDSEvent.detector_name)
        .all()
    )
    return {
        row.source_key: {
            "recent_incident_count": int(row.recent_incident_count or 0),
            "recent_incident_last_seen_at": row.recent_incident_last_seen_at,
        }
        for row in rows
    }


def list_recent_sync_attempts(
    db: Session,
    source_ids: list[int],
    *,
    limit_per_source: int = 3,
) -> dict[int, list[IDSSourceSyncAttempt]]:
    ids = [source_id for source_id in source_ids if source_id]
    if not ids:
        return {}
    rows = (
        db.query(IDSSourceSyncAttempt)
        .filter(IDSSourceSyncAttempt.source_id.in_(ids))
        .order_by(IDSSourceSyncAttempt.started_at.desc(), IDSSourceSyncAttempt.id.desc())
        .all()
    )
    grouped: dict[int, list[IDSSourceSyncAttempt]] = {}
    for row in rows:
        bucket = grouped.setdefault(int(row.source_id), [])
        if len(bucket) < limit_per_source:
            bucket.append(row)
    return grouped
