from __future__ import annotations

from datetime import datetime

from ..models.ids_event import IDSEvent

REAL_EVENT_ORIGIN = "real"
DEMO_EVENT_ORIGIN = "demo"
TEST_EVENT_ORIGIN = "test"

# Event ingestion keeps production provenance classes aligned with the source
# registry. Demo/test-only source records stay in the registry layer instead of
# expanding the normalized event contract.
SOURCE_EXTERNAL_MATURE = "external_mature"
SOURCE_CUSTOM_PROJECT = "custom_project"
SOURCE_TRANSITIONAL_LOCAL = "transitional_local"


def build_event_fingerprint(
    client_ip: str,
    method: str,
    path: str,
    attack_type: str,
    source_rule_id: str = "",
) -> str:
    parts = [
        (client_ip or "").strip(),
        (method or "").strip().upper(),
        (path or "").strip(),
        (attack_type or "").strip(),
        (source_rule_id or "").strip(),
    ]
    return "::".join(parts)[:255]


def build_correlation_key(
    occurred_at: datetime | None,
    client_ip: str,
    attack_type: str,
    detector_name: str,
) -> str:
    bucket = occurred_at.strftime("%Y%m%d%H%M") if occurred_at else "unknown"
    parts = [
        bucket,
        (client_ip or "").strip(),
        (attack_type or "").strip(),
        (detector_name or "").strip(),
    ]
    return "::".join(parts)[:255]


def apply_source_metadata(
    evt: IDSEvent,
    *,
    event_origin: str,
    source_classification: str,
    detector_family: str,
    detector_name: str,
    source_rule_id: str = "",
    source_rule_name: str = "",
    source_version: str = "",
    source_freshness: str = "unknown",
    occurred_at: datetime | None = None,
    event_fingerprint: str = "",
    correlation_key: str = "",
) -> IDSEvent:
    evt.event_origin = event_origin
    evt.source_classification = source_classification
    evt.detector_family = detector_family
    evt.detector_name = detector_name
    evt.source_rule_id = (source_rule_id or "")[:128]
    evt.source_rule_name = (source_rule_name or "")[:128]
    evt.source_version = (source_version or "")[:64]
    evt.source_freshness = (source_freshness or "unknown")[:16]
    evt.event_fingerprint = (
        event_fingerprint
        or build_event_fingerprint(
            evt.client_ip or "",
            evt.method or "",
            evt.path or "",
            evt.attack_type or "",
            evt.source_rule_id or "",
        )
    )
    evt.correlation_key = (
        correlation_key
        or build_correlation_key(
            occurred_at or getattr(evt, "created_at", None),
            evt.client_ip or "",
            evt.attack_type or "",
            evt.detector_name or "",
        )
    )
    return evt
