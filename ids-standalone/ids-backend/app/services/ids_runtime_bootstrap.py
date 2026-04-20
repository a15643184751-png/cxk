from __future__ import annotations

import logging
from datetime import datetime

from ..database import SessionLocal
from ..models.ids_source import IDSSource, IDSSourceSyncAttempt
from ..models.ids_source_package import IDSSourcePackageActivation, IDSSourcePackageIntake
from .ids_engine import refresh_runtime_rule_cache
from .ids_source_ops import (
    SOURCE_DEMO_TEST,
    SOURCE_EXTERNAL_MATURE,
    SOURCE_STATUS_DISABLED,
    SOURCE_STATUS_DRAFT,
    SYNC_MODE_MANUAL,
    SYNC_STATUS_FAILED,
    SYNC_STATUS_NEVER,
    SYNC_STATUS_SUCCESS,
    derive_source_health_state,
    normalize_source_key,
)
from .ids_source_packages import PACKAGE_RESULT_ACTIVATED, PACKAGE_RESULT_PREVIEWED
from .ids_source_sync import SourceSyncValidationError, load_source_sync_payload

logger = logging.getLogger("ids.bootstrap")

DEFAULT_RUNTIME_SOURCE_KEY = "suricata-web-prod"
DEFAULT_RUNTIME_SYNC_ENDPOINT = "app/data/ids_source_sync/suricata-web-prod.manifest.json"
DEFAULT_RUNTIME_SOURCE = {
    "source_key": DEFAULT_RUNTIME_SOURCE_KEY,
    "display_name": "Suricata Mature Web Rules",
    "trust_classification": SOURCE_EXTERNAL_MATURE,
    "detector_family": "web",
    "operational_status": "enabled",
    "freshness_target_hours": 24,
    "sync_mode": SYNC_MODE_MANUAL,
    "sync_endpoint": DEFAULT_RUNTIME_SYNC_ENDPOINT,
    "provenance_note": (
        "Local mirror of mature Suricata-compatible web attack signatures, "
        "bootstrapped for the IDS security center."
    ),
}


def bootstrap_ids_runtime_source() -> dict[str, object]:
    summary: dict[str, object] = {
        "source_key": DEFAULT_RUNTIME_SOURCE_KEY,
        "created_source": False,
        "created_intake": False,
        "activated": False,
        "rule_count": 0,
        "package_version": "",
        "status": "unchanged",
    }
    db = SessionLocal()
    try:
        source, created_source = _ensure_default_source(db)
        summary["created_source"] = created_source
        summary["source_id"] = int(source.id)

        # Respect existing operator-managed active web sources.
        if _has_operator_managed_active_web_source(db, exclude_source_id=int(source.id)):
            rule_count = len(refresh_runtime_rule_cache(force=True))
            summary["rule_count"] = rule_count
            summary["status"] = "using_existing_active_source"
            return summary

        if (source.trust_classification or "").strip() == SOURCE_DEMO_TEST:
            summary["status"] = "skipped_demo_source"
            summary["rule_count"] = len(refresh_runtime_rule_cache(force=True))
            return summary

        if (source.operational_status or "").strip() in {SOURCE_STATUS_DISABLED, SOURCE_STATUS_DRAFT}:
            summary["status"] = f"skipped_{source.operational_status or 'disabled'}"
            summary["rule_count"] = len(refresh_runtime_rule_cache(force=True))
            return summary

        sync_payload = load_source_sync_payload(source)
        package_version = str(sync_payload.get("package_version") or "")[:64]
        artifact_sha256 = str(sync_payload.get("artifact_sha256") or "")[:64]
        rule_count = int(sync_payload.get("rule_count") or 0)
        summary["package_version"] = package_version
        summary["rule_count"] = rule_count

        intake = _find_matching_intake(
            db,
            source_id=int(source.id),
            package_version=package_version,
            artifact_sha256=artifact_sha256,
        )
        if intake is None:
            intake = IDSSourcePackageIntake(
                source_id=source.id,
                source_key=source.source_key or DEFAULT_RUNTIME_SOURCE_KEY,
                package_version=package_version,
                release_timestamp=sync_payload.get("release_timestamp"),
                trust_classification=str(sync_payload.get("trust_classification") or source.trust_classification or ""),
                detector_family=str(sync_payload.get("detector_family") or source.detector_family or "web"),
                provenance_note=str(sync_payload.get("provenance_note") or source.provenance_note or ""),
                intake_result=PACKAGE_RESULT_PREVIEWED,
                intake_detail=str(sync_payload.get("sync_detail") or "runtime bootstrap synchronized source package")[:1000],
                artifact_path=str(sync_payload.get("artifact_path") or "")[:255],
                artifact_sha256=artifact_sha256,
                artifact_size_bytes=int(sync_payload.get("artifact_size_bytes") or 0),
                rule_count=rule_count,
                triggered_by="system_bootstrap",
            )
            db.add(intake)
            db.flush()
            summary["created_intake"] = True

        latest_activation = (
            db.query(IDSSourcePackageActivation)
            .filter(IDSSourcePackageActivation.source_id == source.id)
            .order_by(IDSSourcePackageActivation.activated_at.desc(), IDSSourcePackageActivation.id.desc())
            .first()
        )
        activation_needed = latest_activation is None or (latest_activation.package_version or "") != package_version
        if activation_needed:
            activation = IDSSourcePackageActivation(
                source_id=source.id,
                package_intake_id=int(intake.id),
                package_version=package_version,
                activated_by="system_bootstrap",
                activation_detail="Startup bootstrap activated the current IDS static rule package.",
            )
            db.add(activation)
            intake.intake_result = PACKAGE_RESULT_ACTIVATED
            intake.intake_detail = "system_bootstrap activated current runtime package"
            summary["activated"] = True

        now = datetime.utcnow()
        detail = str(sync_payload.get("sync_detail") or "runtime bootstrap synchronized source package")[:1000]
        state_changed = bool(summary["created_source"] or summary["created_intake"] or summary["activated"])
        source.last_synced_at = now
        source.last_sync_status = SYNC_STATUS_SUCCESS
        source.last_sync_detail = detail
        if state_changed or (not source.last_synced_at) or (source.last_sync_status or "") != SYNC_STATUS_SUCCESS:
            attempt = IDSSourceSyncAttempt(
                source_id=source.id,
                started_at=now,
                finished_at=now,
                result_status=SYNC_STATUS_SUCCESS,
                detail=detail,
                freshness_after_sync=derive_source_health_state(source, now=now),
                package_version=package_version,
                package_intake_id=int(intake.id),
                resolved_sync_endpoint=str(sync_payload.get("manifest_path") or source.sync_endpoint or "")[:255],
                triggered_by="system_bootstrap",
            )
            db.add(attempt)

        db.commit()
        summary["status"] = "bootstrapped" if state_changed else "ready"
    except SourceSyncValidationError as exc:
        db.rollback()
        logger.warning("IDS runtime bootstrap validation failed: %s", exc)
        summary["status"] = "failed"
        summary["detail"] = str(exc)
        _mark_bootstrap_failure(db, str(exc))
    except Exception as exc:
        db.rollback()
        logger.warning("IDS runtime bootstrap failed: %s", exc)
        summary["status"] = "failed"
        summary["detail"] = str(exc)
        _mark_bootstrap_failure(db, str(exc))
    finally:
        db.close()

    try:
        summary["rule_count"] = len(refresh_runtime_rule_cache(force=True))
    except Exception as exc:
        logger.warning("IDS runtime cache refresh after bootstrap failed: %s", exc)
    return summary


def _ensure_default_source(db) -> tuple[IDSSource, bool]:
    source_key = normalize_source_key(DEFAULT_RUNTIME_SOURCE_KEY)
    source = db.query(IDSSource).filter(IDSSource.source_key == source_key).first()
    if source:
        if not (source.sync_endpoint or "").strip():
            source.sync_endpoint = DEFAULT_RUNTIME_SYNC_ENDPOINT
        if not (source.display_name or "").strip():
            source.display_name = str(DEFAULT_RUNTIME_SOURCE["display_name"])
        if not int(source.freshness_target_hours or 0):
            source.freshness_target_hours = int(DEFAULT_RUNTIME_SOURCE["freshness_target_hours"])
        if not (source.provenance_note or "").strip():
            source.provenance_note = str(DEFAULT_RUNTIME_SOURCE["provenance_note"])
        db.flush()
        return source, False

    source = IDSSource(
        source_key=source_key,
        display_name=str(DEFAULT_RUNTIME_SOURCE["display_name"]),
        trust_classification=str(DEFAULT_RUNTIME_SOURCE["trust_classification"]),
        detector_family=str(DEFAULT_RUNTIME_SOURCE["detector_family"]),
        operational_status=str(DEFAULT_RUNTIME_SOURCE["operational_status"]),
        freshness_target_hours=int(DEFAULT_RUNTIME_SOURCE["freshness_target_hours"]),
        sync_mode=str(DEFAULT_RUNTIME_SOURCE["sync_mode"]),
        sync_endpoint=str(DEFAULT_RUNTIME_SOURCE["sync_endpoint"]),
        provenance_note=str(DEFAULT_RUNTIME_SOURCE["provenance_note"]),
        last_sync_status=SYNC_STATUS_NEVER,
        last_sync_detail="Awaiting initial runtime bootstrap.",
    )
    db.add(source)
    db.flush()
    return source, True


def _has_operator_managed_active_web_source(db, *, exclude_source_id: int) -> bool:
    rows = (
        db.query(IDSSourcePackageActivation, IDSSource)
        .join(IDSSource, IDSSource.id == IDSSourcePackageActivation.source_id)
        .filter(IDSSourcePackageActivation.source_id != exclude_source_id)
        .filter(IDSSource.detector_family == "web")
        .filter(IDSSource.trust_classification != SOURCE_DEMO_TEST)
        .filter(IDSSource.operational_status != SOURCE_STATUS_DISABLED)
        .order_by(IDSSourcePackageActivation.activated_at.desc(), IDSSourcePackageActivation.id.desc())
        .all()
    )
    return bool(rows)


def _find_matching_intake(db, *, source_id: int, package_version: str, artifact_sha256: str) -> IDSSourcePackageIntake | None:
    rows = (
        db.query(IDSSourcePackageIntake)
        .filter(IDSSourcePackageIntake.source_id == source_id)
        .filter(IDSSourcePackageIntake.package_version == package_version)
        .order_by(IDSSourcePackageIntake.created_at.desc(), IDSSourcePackageIntake.id.desc())
        .all()
    )
    for row in rows:
        if artifact_sha256 and (row.artifact_sha256 or "") == artifact_sha256:
            return row
    return rows[0] if rows else None


def _mark_bootstrap_failure(db, detail: str) -> None:
    try:
        source = db.query(IDSSource).filter(IDSSource.source_key == DEFAULT_RUNTIME_SOURCE_KEY).first()
        if not source:
            return
        source.last_sync_status = SYNC_STATUS_FAILED
        source.last_sync_detail = detail[:1000]
        db.commit()
    except Exception:
        db.rollback()
