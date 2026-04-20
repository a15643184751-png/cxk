from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class IDSSource(Base):
    __tablename__ = "ids_sources"

    id = Column(Integer, primary_key=True, index=True)
    source_key = Column(String(128), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    trust_classification = Column(String(32), nullable=False, default="external_mature", index=True)
    detector_family = Column(String(32), nullable=False, default="", index=True)
    operational_status = Column(String(32), nullable=False, default="enabled", index=True)
    freshness_target_hours = Column(Integer, nullable=False, default=24)
    sync_mode = Column(String(32), nullable=False, default="manual")
    sync_endpoint = Column(String(255), default="")
    last_synced_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_sync_status = Column(String(32), nullable=False, default="never_synced", index=True)
    last_sync_detail = Column(Text, default="")
    provenance_note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    sync_attempts = relationship(
        "IDSSourceSyncAttempt",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="desc(IDSSourceSyncAttempt.started_at)",
    )
    package_intakes = relationship(
        "IDSSourcePackageIntake",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="desc(IDSSourcePackageIntake.created_at)",
    )
    package_activations = relationship(
        "IDSSourcePackageActivation",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="desc(IDSSourcePackageActivation.activated_at)",
    )


class IDSSourceSyncAttempt(Base):
    __tablename__ = "ids_source_sync_attempts"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("ids_sources.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    result_status = Column(String(32), nullable=False, default="success", index=True)
    detail = Column(Text, default="")
    freshness_after_sync = Column(String(32), default="")
    package_version = Column(String(64), default="")
    package_intake_id = Column(Integer, nullable=True)
    resolved_sync_endpoint = Column(String(255), default="")
    triggered_by = Column(String(64), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    source = relationship("IDSSource", back_populates="sync_attempts")
