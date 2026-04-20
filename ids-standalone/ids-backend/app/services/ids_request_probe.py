"""Shared request-detection persistence for middleware and browser-route probes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models.ids_event import IDSEvent
from .ids_ai_analysis import schedule_ai_analysis
from .ids_engine import block_ip_windows
from .ids_ingestion import REAL_EVENT_ORIGIN, SOURCE_TRANSITIONAL_LOCAL, apply_source_metadata
from .ids_operator_hub import auto_dispatch_notifications_for_event, serialize_notification_event


def persist_request_detection(
    db: Session,
    *,
    client_ip: str,
    method: str,
    path: str,
    query: str,
    body_str: str,
    headers: dict[str, Any],
    user_agent: str,
    detection: dict[str, Any],
    event_origin: str = REAL_EVENT_ORIGIN,
) -> dict[str, Any]:
    attack_type = str(detection.get("attack_type") or "")
    signature_matched = str(detection.get("signature_matched") or "")
    risk_score = int(detection.get("risk_score") or 0)
    confidence = int(detection.get("confidence") or 0)
    hit_count = int(detection.get("hit_count") or 0)
    detect_detail = str(detection.get("detect_detail") or "")
    source_classification = str(detection.get("source_classification") or SOURCE_TRANSITIONAL_LOCAL)
    detector_family = str(detection.get("detector_family") or "web")
    detector_name = str(detection.get("detector_name") or "inline_request_matcher")
    source_rule_id = str(detection.get("source_rule_id") or signature_matched[:128])
    source_rule_name = str(detection.get("source_rule_name") or attack_type)
    source_version = str(detection.get("source_version") or "legacy-inline")
    source_freshness = str(detection.get("source_freshness") or "current")
    should_block = risk_score >= int(settings.IDS_BLOCK_THRESHOLD)

    blocked = 0
    firewall_rule = ""
    status = "investigating"
    action_taken = "record_only"
    response_result = "record_only"
    response_detail = "recorded_without_block"

    if should_block:
        blocked = 1
        action_taken = "logical_block_only"
        response_result = "success"
        response_detail = "threshold_reached_without_firewall"
        if settings.IDS_FIREWALL_BLOCK:
            try:
                ok, msg = block_ip_windows(client_ip)
                if ok:
                    firewall_rule = msg
                    action_taken = "firewall_block"
                    response_detail = msg
                elif msg:
                    response_detail = msg
            except Exception as exc:
                response_detail = str(exc)

    evt_id: int | None = None
    try:
        evt = IDSEvent(
            client_ip=client_ip,
            attack_type=attack_type,
            signature_matched=signature_matched[:128],
            method=method[:16],
            path=path[:512],
            query_snippet=query[:500],
            body_snippet=(body_str or "")[:500],
            user_agent=user_agent[:512],
            headers_snippet=str(headers)[:1000],
            blocked=blocked,
            firewall_rule=firewall_rule[:256],
            status=status,
            action_taken=action_taken,
            response_result=response_result,
            response_detail=response_detail[:1000],
            risk_score=risk_score,
            confidence=confidence,
            hit_count=hit_count,
            detect_detail=detect_detail,
        )
        apply_source_metadata(
            evt,
            event_origin=event_origin,
            source_classification=source_classification[:32],
            detector_family=detector_family[:32],
            detector_name=detector_name[:64],
            source_rule_id=source_rule_id[:128],
            source_rule_name=source_rule_name[:128],
            source_version=source_version[:64],
            source_freshness=source_freshness[:16],
        )
        db.add(evt)
        db.commit()
        db.refresh(evt)
        evt_id = int(evt.id)
    except Exception:
        db.rollback()
        raise

    if evt_id is not None:
        schedule_ai_analysis(evt_id)
        auto_dispatch_notifications_for_event(
            db,
            serialize_notification_event(evt),
            source="request_probe",
        )
        db.commit()

    return {
        "incident_id": evt_id,
        "blocked": blocked == 1,
        "should_block": should_block,
        "attack_type": attack_type,
        "risk_score": risk_score,
        "confidence": confidence,
        "response_detail": response_detail[:1000],
    }
