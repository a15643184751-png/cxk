from __future__ import annotations

from pathlib import Path

from .config import settings
from .core.security import get_password_hash
from .database import SessionLocal
from .models.user import User


def ensure_runtime_dirs() -> None:
    for raw_path in (
        settings.IDS_ACCEPTED_UPLOAD_DIR,
        settings.IDS_QUARANTINE_DIR,
        settings.IDS_REPORT_DIR,
        settings.IDS_OPERATOR_STATE_DIR,
    ):
        Path(raw_path).mkdir(parents=True, exist_ok=True)


def ensure_default_ids_admin() -> User:
    ensure_runtime_dirs()

    db = SessionLocal()
    try:
        admin = (
            db.query(User)
            .filter(User.username == settings.IDS_DEFAULT_ADMIN_USERNAME)
            .first()
        )
        if admin:
            if admin.role != "ids_admin":
                admin.role = "ids_admin"
                db.commit()
                db.refresh(admin)
            return admin

        admin = User(
            username=settings.IDS_DEFAULT_ADMIN_USERNAME,
            hashed_password=get_password_hash(settings.IDS_DEFAULT_ADMIN_PASSWORD),
            real_name=settings.IDS_DEFAULT_ADMIN_REAL_NAME,
            role="ids_admin",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin
    finally:
        db.close()
