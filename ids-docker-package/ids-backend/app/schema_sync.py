from sqlalchemy import inspect, text

from .database import Base
from .models.ids_source import IDSSource, IDSSourceSyncAttempt
from .models.ids_source_package import IDSSourcePackageActivation, IDSSourcePackageIntake


SCHEMA_PATCHES: dict[str, dict[str, str]] = {
    "ids_sources": {
        "sync_endpoint": "VARCHAR(255)",
    },
    "ids_source_sync_attempts": {
        "package_version": "VARCHAR(64)",
        "package_intake_id": "INTEGER",
        "resolved_sync_endpoint": "VARCHAR(255)",
    },
    "ids_source_package_intakes": {
        "artifact_path": "VARCHAR(255)",
        "artifact_sha256": "VARCHAR(64)",
        "artifact_size_bytes": "INTEGER",
        "rule_count": "INTEGER",
    },
    "ids_events": {
        "event_origin": "VARCHAR(16)",
        "source_classification": "VARCHAR(32)",
        "detector_family": "VARCHAR(32)",
        "detector_name": "VARCHAR(64)",
        "source_rule_id": "VARCHAR(128)",
        "source_rule_name": "VARCHAR(128)",
        "source_version": "VARCHAR(64)",
        "source_freshness": "VARCHAR(16)",
        "event_fingerprint": "VARCHAR(255)",
        "correlation_key": "VARCHAR(255)",
        "ai_analysis": "TEXT",
        "ai_risk_level": "VARCHAR(32)",
        "ai_confidence": "INTEGER",
        "ai_analyzed_at": "DATETIME",
        "status": "VARCHAR(32)",
        "review_note": "TEXT",
        "action_taken": "VARCHAR(128)",
        "response_result": "VARCHAR(32)",
        "response_detail": "TEXT",
        "risk_score": "INTEGER",
        "confidence": "INTEGER",
        "hit_count": "INTEGER",
        "detect_detail": "TEXT",
    },
}


def ensure_schema(engine):
    Base.metadata.create_all(
        bind=engine,
        tables=[
            IDSSource.__table__,
            IDSSourceSyncAttempt.__table__,
            IDSSourcePackageIntake.__table__,
            IDSSourcePackageActivation.__table__,
        ],
    )
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in SCHEMA_PATCHES.items():
            existing = {col["name"] for col in inspector.get_columns(table)} if inspector.has_table(table) else set()
            for name, column_type in columns.items():
                if name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))
        _ensure_ids_source_package_intake_source_nullable(conn, engine)


def _ensure_ids_source_package_intake_source_nullable(conn, engine):
    inspector = inspect(engine)
    if not inspector.has_table("ids_source_package_intakes"):
        return

    source_id_col = None
    for column in inspector.get_columns("ids_source_package_intakes"):
        if column["name"] == "source_id":
            source_id_col = column
            break
    if not source_id_col or source_id_col.get("nullable", True):
        return

    if engine.dialect.name == "sqlite":
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ids_source_package_intakes__new (
                id INTEGER NOT NULL PRIMARY KEY,
                source_id INTEGER,
                source_key VARCHAR(128) NOT NULL,
                package_version VARCHAR(64) NOT NULL,
                release_timestamp DATETIME,
                trust_classification VARCHAR(32) NOT NULL,
                detector_family VARCHAR(32) NOT NULL,
                provenance_note TEXT,
                intake_result VARCHAR(32) NOT NULL,
                intake_detail TEXT,
                artifact_path VARCHAR(255),
                artifact_sha256 VARCHAR(64),
                artifact_size_bytes INTEGER,
                rule_count INTEGER,
                triggered_by VARCHAR(64),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_id) REFERENCES ids_sources (id)
            )
        """))
        conn.execute(text("""
            INSERT INTO ids_source_package_intakes__new (
                id, source_id, source_key, package_version, release_timestamp,
                trust_classification, detector_family, provenance_note,
                intake_result, intake_detail, artifact_path, artifact_sha256,
                artifact_size_bytes, rule_count, triggered_by, created_at
            )
            SELECT
                id, source_id, source_key, package_version, release_timestamp,
                trust_classification, detector_family, provenance_note,
                intake_result, intake_detail, artifact_path, artifact_sha256,
                artifact_size_bytes, rule_count, triggered_by, created_at
            FROM ids_source_package_intakes
        """))
        conn.execute(text("DROP TABLE ids_source_package_intakes"))
        conn.execute(text("ALTER TABLE ids_source_package_intakes__new RENAME TO ids_source_package_intakes"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_source_id ON ids_source_package_intakes (source_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_source_key ON ids_source_package_intakes (source_key)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_package_version ON ids_source_package_intakes (package_version)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_release_timestamp ON ids_source_package_intakes (release_timestamp)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_trust_classification ON ids_source_package_intakes (trust_classification)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_detector_family ON ids_source_package_intakes (detector_family)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_intake_result ON ids_source_package_intakes (intake_result)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ids_source_package_intakes_created_at ON ids_source_package_intakes (created_at)"))
        return

    conn.execute(text("ALTER TABLE ids_source_package_intakes ALTER COLUMN source_id DROP NOT NULL"))
