from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class IDSSourcePackageIntake(Base):
    __tablename__ = "ids_source_package_intakes"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("ids_sources.id"), nullable=True, index=True)
    source_key = Column(String(128), nullable=False, index=True)
    package_version = Column(String(64), nullable=False, index=True)
    release_timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    trust_classification = Column(String(32), nullable=False, index=True)
    detector_family = Column(String(32), nullable=False, index=True)
    provenance_note = Column(Text, default="")
    intake_result = Column(String(32), nullable=False, default="previewed", index=True)
    intake_detail = Column(Text, default="")
    artifact_path = Column(String(255), default="")
    artifact_sha256 = Column(String(64), default="")
    artifact_size_bytes = Column(Integer, nullable=True)
    rule_count = Column(Integer, nullable=True)
    triggered_by = Column(String(64), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    source = relationship("IDSSource", back_populates="package_intakes")
    activations = relationship(
        "IDSSourcePackageActivation",
        back_populates="package_intake",
        cascade="all, delete-orphan",
        order_by="desc(IDSSourcePackageActivation.activated_at)",
    )


class IDSSourcePackageActivation(Base):
    __tablename__ = "ids_source_package_activations"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("ids_sources.id"), nullable=False, index=True)
    package_intake_id = Column(Integer, ForeignKey("ids_source_package_intakes.id"), nullable=False, index=True)
    package_version = Column(String(64), nullable=False, index=True)
    activated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    activated_by = Column(String(64), default="")
    activation_detail = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    source = relationship("IDSSource", back_populates="package_activations")
    package_intake = relationship("IDSSourcePackageIntake", back_populates="activations")
