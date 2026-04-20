from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String(32), unique=True, nullable=False, index=True)
    status = Column(String(32), default="pending")  # pending, approved, confirmed, stocked_in, stocked_out, delivering, completed, rejected
    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_reason = Column(String(256), nullable=True)
    destination = Column(String(200), default="")
    receiver_name = Column(String(50), default="")
    handoff_code = Column(String(64), default="")

    # 教师申请增强字段
    material_type = Column(String(32), default="")  # 教学/科研/办公
    material_spec = Column(String(128), default="")
    estimated_amount = Column(Float, default=0)
    delivery_date = Column(DateTime(timezone=True), nullable=True)
    attachment_names = Column(String(512), default="")
    is_draft = Column(Integer, default=0)
    urgent_level = Column(String(16), default="normal")  # normal / urgent

    # 分级审批字段
    approval_level = Column(String(32), default="minor")
    approval_required_role = Column(String(32), default="logistics_admin")
    approval_deadline_at = Column(DateTime(timezone=True), nullable=True)
    forwarded_to = Column(String(64), default="")
    forwarded_note = Column(String(256), default="")
    ai_judgment = Column(String(16), default="")  # pass/cautious/reject
    ai_judgment_score = Column(Integer, default=0)
    ai_judgment_summary = Column(String(512), default="")
    ai_judgment_at = Column(DateTime(timezone=True), nullable=True)
    ai_dimension_inventory = Column(String(32), default="")
    ai_dimension_budget = Column(String(32), default="")
    ai_dimension_price = Column(String(32), default="")
    ai_dimension_compliance = Column(String(32), default="")
    ai_dimension_supplier = Column(String(32), default="")
    approval_opinion = Column(String(512), default="")
    approval_reason_option = Column(String(128), default="")
    approval_signature_mode = Column(String(32), default="")  # draw/stamp
    approval_signature_data = Column(String(2048), default="")
    approval_signed_at = Column(DateTime(timezone=True), nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("PurchaseItem", back_populates="purchase")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    goods_name = Column(String(128), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(32), default="")

    purchase = relationship("Purchase", back_populates="items")

