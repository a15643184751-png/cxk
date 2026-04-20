from sqlalchemy import inspect, text


SCHEMA_PATCHES: dict[str, dict[str, str]] = {
    "ids_events": {
        "ai_analysis": "TEXT",
        "ai_risk_level": "VARCHAR(32)",
        "ai_confidence": "INTEGER",
        "ai_analyzed_at": "DATETIME",
        "status": "VARCHAR(32)",
        "review_note": "TEXT",
        "action_taken": "VARCHAR(128)",
        "risk_score": "INTEGER",
        "confidence": "INTEGER",
        "hit_count": "INTEGER",
        "detect_detail": "TEXT",
    },
    "purchases": {
        "approved_by_id": "INTEGER",
        "rejected_reason": "TEXT",
        "destination": "VARCHAR(200)",
        "receiver_name": "VARCHAR(50)",
        "handoff_code": "VARCHAR(64)",
        "material_type": "VARCHAR(32)",
        "material_spec": "VARCHAR(128)",
        "estimated_amount": "FLOAT",
        "delivery_date": "DATETIME",
        "attachment_names": "VARCHAR(512)",
        "is_draft": "INTEGER",
        "urgent_level": "VARCHAR(16)",
        "approval_level": "VARCHAR(32)",
        "approval_required_role": "VARCHAR(32)",
        "approval_deadline_at": "DATETIME",
        "forwarded_to": "VARCHAR(64)",
        "forwarded_note": "VARCHAR(256)",
        "ai_judgment": "VARCHAR(16)",
        "ai_judgment_score": "INTEGER",
        "ai_judgment_summary": "VARCHAR(512)",
        "ai_judgment_at": "DATETIME",
        "ai_dimension_inventory": "VARCHAR(32)",
        "ai_dimension_budget": "VARCHAR(32)",
        "ai_dimension_price": "VARCHAR(32)",
        "ai_dimension_compliance": "VARCHAR(32)",
        "ai_dimension_supplier": "VARCHAR(32)",
        "approval_opinion": "VARCHAR(512)",
        "approval_reason_option": "VARCHAR(128)",
        "approval_signature_mode": "VARCHAR(32)",
        "approval_signature_data": "VARCHAR(2048)",
        "approval_signed_at": "DATETIME",
        "completed_at": "DATETIME",
    },
    "stock_ins": {
        "purchase_id": "INTEGER",
    },
    "stock_outs": {
        "purchase_id": "INTEGER",
        "destination": "VARCHAR(200)",
        "receiver_name": "VARCHAR(50)",
        "handoff_code": "VARCHAR(64)",
    },
    "deliveries": {
        "purchase_id": "INTEGER",
        "receiver_user_id": "INTEGER",
        "handoff_code": "VARCHAR(64)",
        "confirmed_by_id": "INTEGER",
        "confirmed_at": "DATETIME",
        "sign_remark": "TEXT",
    },
}


def ensure_schema(engine):
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in SCHEMA_PATCHES.items():
            existing = {col["name"] for col in inspector.get_columns(table)} if inspector.has_table(table) else set()
            for name, column_type in columns.items():
                if name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))
