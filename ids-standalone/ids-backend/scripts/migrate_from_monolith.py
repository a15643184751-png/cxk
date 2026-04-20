from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
IDS_BACKEND_DIR = SCRIPT_DIR.parent
REPO_ROOT = IDS_BACKEND_DIR.parent
if str(IDS_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(IDS_BACKEND_DIR))

from app.bootstrap import ensure_default_ids_admin, ensure_runtime_dirs
from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401,F403
from app.schema_sync import ensure_schema


def env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def first_existing_path(*candidates: Path | None) -> Path | None:
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    return None


LEGACY_MONOLITH_ROOT = first_existing_path(
    env_path("IDS_LEGACY_MONOLITH_ROOT"),
    REPO_ROOT.parent / "gongyinglian" / "workspace" / "CampusSupplyChainSecurityPlatform",
    REPO_ROOT.parent / "workspace" / "CampusSupplyChainSecurityPlatform",
    REPO_ROOT.parent / "CampusSupplyChainSecurityPlatform",
    REPO_ROOT,
)
LEGACY_BACKEND_DIR = first_existing_path(
    env_path("IDS_LEGACY_BACKEND_DIR"),
    (LEGACY_MONOLITH_ROOT / "backend") if LEGACY_MONOLITH_ROOT else None,
    REPO_ROOT / "backend",
)

DEFAULT_SOURCE_DB = env_path("IDS_LEGACY_SOURCE_DB") or (
    (LEGACY_BACKEND_DIR / "supply_chain.db")
    if LEGACY_BACKEND_DIR
    else REPO_ROOT / "backend" / "supply_chain.db"
)
DEFAULT_ACCEPTED_DIR = env_path("IDS_LEGACY_ACCEPTED_DIR") or (
    (LEGACY_BACKEND_DIR / "uploads" / "accepted")
    if LEGACY_BACKEND_DIR
    else REPO_ROOT / "backend" / "uploads" / "accepted"
)
DEFAULT_QUARANTINE_DIR = env_path("IDS_LEGACY_QUARANTINE_DIR") or (
    (LEGACY_BACKEND_DIR / "quarantine_uploads")
    if LEGACY_BACKEND_DIR
    else REPO_ROOT / "backend" / "quarantine_uploads"
)
DEFAULT_REPORT_DIR = env_path("IDS_LEGACY_REPORT_DIR") or (
    (LEGACY_BACKEND_DIR / "upload_reports")
    if LEGACY_BACKEND_DIR
    else REPO_ROOT / "backend" / "upload_reports"
)
DEFAULT_STATE_DIR = env_path("IDS_LEGACY_STATE_DIR") or (
    (LEGACY_BACKEND_DIR / "app" / "data" / "ids_operator_state")
    if LEGACY_BACKEND_DIR
    else REPO_ROOT / "backend" / "app" / "data" / "ids_operator_state"
)

ROLE_MAP = {
    "system_admin": "ids_admin",
    "admin": "ids_admin",
    "logistics_admin": "ids_operator",
    "warehouse_procurement": "ids_operator",
    "counselor_teacher": "ids_viewer",
    "campus_supplier": "ids_viewer",
}


def resolve_target_sqlite_path() -> Path:
    prefix = "sqlite:///"
    if not settings.DATABASE_URL.startswith(prefix):
        raise SystemExit(
            "This migration script currently supports only SQLite targets. "
            f"Current DATABASE_URL={settings.DATABASE_URL}"
        )

    raw = settings.DATABASE_URL[len(prefix) :]
    target = Path(raw)
    if not target.is_absolute():
        target = (IDS_BACKEND_DIR / target).resolve()
    return target


def existing_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def copy_table(
    source_conn: sqlite3.Connection,
    target_conn: sqlite3.Connection,
    *,
    source_table: str,
    target_table: str,
) -> int:
    source_cols = existing_columns(source_conn, source_table)
    target_cols = existing_columns(target_conn, target_table)
    common_cols = [col for col in source_cols if col in target_cols]
    if not common_cols:
        return 0

    query = f"SELECT {', '.join(common_cols)} FROM {source_table}"
    rows = source_conn.execute(query).fetchall()
    placeholders = ", ".join("?" for _ in common_cols)
    target_conn.execute(f"DELETE FROM {target_table}")
    if rows:
        target_conn.executemany(
            f"INSERT INTO {target_table} ({', '.join(common_cols)}) VALUES ({placeholders})",
            rows,
        )
    return len(rows)


def migrate_users(source_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
    rows = source_conn.execute(
        """
        SELECT id, username, hashed_password, real_name, role, department, phone
        FROM users
        ORDER BY id ASC
        """
    ).fetchall()

    target_conn.execute("DELETE FROM ids_users")
    inserted = 0
    for row in rows:
        role = ROLE_MAP.get(str(row[4] or "").strip())
        if not role:
            continue

        username = str(row[1] or "").strip()
        if username in {"system_admin", "admin"}:
            username = settings.IDS_DEFAULT_ADMIN_USERNAME

        target_conn.execute(
            """
            INSERT INTO ids_users (id, username, hashed_password, real_name, role, department, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                username,
                row[2],
                row[3] or username,
                role,
                row[5] or "",
                row[6] or "",
            ),
        )
        inserted += 1
    return inserted


def migrate_audit_logs(source_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> int:
    rows = source_conn.execute(
        """
        SELECT id, user_id, user_name, user_role, action, target_type, target_id, detail, created_at
        FROM audit_logs
        ORDER BY id ASC
        """
    ).fetchall()

    target_conn.execute("DELETE FROM ids_audit_logs")
    inserted = 0
    for row in rows:
        action = str(row[4] or "").strip()
        target_type = str(row[5] or "").strip()
        if not (
            action.startswith("ids_")
            or target_type
            in {
                "ids_event",
                "public_upload",
                "sandbox_file",
                "ids_source",
                "source_package",
                "browser_route",
            }
        ):
            continue

        target_conn.execute(
            """
            INSERT INTO ids_audit_logs (
                id, user_id, user_name, user_role, action, target_type, target_id, detail, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2] or "",
                ROLE_MAP.get(str(row[3] or "").strip(), str(row[3] or "").strip()),
                action,
                target_type,
                row[6] or "",
                row[7] or "",
                row[8],
            ),
        )
        inserted += 1
    return inserted


def copy_runtime_tree(source_dir: Path, target_dir: Path) -> int:
    if not source_dir.exists():
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in source_dir.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(source_dir)
        destination = target_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        copied += 1
    return copied


def main() -> None:
    if not DEFAULT_SOURCE_DB.exists():
        raise SystemExit(
            "Legacy source database not found. "
            "Set IDS_LEGACY_MONOLITH_ROOT or IDS_LEGACY_SOURCE_DB first. "
            f"Expected path: {DEFAULT_SOURCE_DB}"
        )

    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    ensure_runtime_dirs()

    target_db_path = resolve_target_sqlite_path()
    target_db_path.parent.mkdir(parents=True, exist_ok=True)

    source_conn = sqlite3.connect(DEFAULT_SOURCE_DB)
    target_conn = sqlite3.connect(target_db_path)
    try:
        counts = {
            "ids_users": migrate_users(source_conn, target_conn),
            "ids_audit_logs": migrate_audit_logs(source_conn, target_conn),
            "ids_events": copy_table(
                source_conn,
                target_conn,
                source_table="ids_events",
                target_table="ids_events",
            ),
            "ids_sources": copy_table(
                source_conn,
                target_conn,
                source_table="ids_sources",
                target_table="ids_sources",
            ),
            "ids_source_sync_attempts": copy_table(
                source_conn,
                target_conn,
                source_table="ids_source_sync_attempts",
                target_table="ids_source_sync_attempts",
            ),
            "ids_source_package_intakes": copy_table(
                source_conn,
                target_conn,
                source_table="ids_source_package_intakes",
                target_table="ids_source_package_intakes",
            ),
            "ids_source_package_activations": copy_table(
                source_conn,
                target_conn,
                source_table="ids_source_package_activations",
                target_table="ids_source_package_activations",
            ),
        }
        target_conn.commit()
    finally:
        source_conn.close()
        target_conn.close()

    ensure_default_ids_admin()

    copied_files = {
        "accepted": copy_runtime_tree(
            DEFAULT_ACCEPTED_DIR,
            Path(settings.IDS_ACCEPTED_UPLOAD_DIR),
        ),
        "quarantine": copy_runtime_tree(
            DEFAULT_QUARANTINE_DIR,
            Path(settings.IDS_QUARANTINE_DIR),
        ),
        "reports": copy_runtime_tree(
            DEFAULT_REPORT_DIR,
            Path(settings.IDS_REPORT_DIR),
        ),
        "state": copy_runtime_tree(
            DEFAULT_STATE_DIR,
            Path(settings.IDS_OPERATOR_STATE_DIR),
        ),
    }

    print("[migrate] source_db=", DEFAULT_SOURCE_DB)
    print("[migrate] target_db=", target_db_path)
    if LEGACY_BACKEND_DIR:
        print("[migrate] legacy_backend_dir=", LEGACY_BACKEND_DIR)
    for table, count in counts.items():
        print(f"[migrate] {table}={count}")
    for name, count in copied_files.items():
        print(f"[migrate] files_{name}={count}")
    print(
        "[migrate] default admin ready: "
        f"username={settings.IDS_DEFAULT_ADMIN_USERNAME}, "
        f"password={settings.IDS_DEFAULT_ADMIN_PASSWORD}"
    )


if __name__ == "__main__":
    main()
