from __future__ import annotations

from app.bootstrap import ensure_default_ids_admin, ensure_runtime_dirs
from app.config import settings
from app.database import Base, engine
from app.models import *  # noqa: F401,F403
from app.schema_sync import ensure_schema


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    ensure_runtime_dirs()
    admin = ensure_default_ids_admin()

    print("[init] IDS database is ready")
    print(f"[init] database={settings.DATABASE_URL}")
    print(f"[init] accepted_dir={settings.IDS_ACCEPTED_UPLOAD_DIR}")
    print(f"[init] quarantine_dir={settings.IDS_QUARANTINE_DIR}")
    print(f"[init] report_dir={settings.IDS_REPORT_DIR}")
    print(f"[init] state_dir={settings.IDS_OPERATOR_STATE_DIR}")
    print(
        "[init] default admin: "
        f"username={admin.username}, password={settings.IDS_DEFAULT_ADMIN_PASSWORD}"
    )


if __name__ == "__main__":
    main()
