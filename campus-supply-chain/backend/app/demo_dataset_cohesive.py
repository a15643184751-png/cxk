"""
Cohesive campus demo dataset: purge legacy noise (SI-DEMO, PO202603*, SN-DEMO, etc.),
then insert full POCHAIN-* purchase lifecycles with trace, delivery, stock in/out, inventory.

Idempotent marker: audit_logs action=_cohesive_demo_v2
Force reset: python -m app.demo_dataset_cohesive --force
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .demo_random_purchases import seed_random_purchase_orders
from .services.inventory_ledger import rebuild_inventory_from_ledger

MARKER_ACTION = "_cohesive_demo_v2"
MARKER_TARGET = "applied"

# All goods names used in init_db DEMO_GOODS (inventory reset scope)
DEMO_GOOD_NAMES: tuple[str, ...] = (
    "\u5927\u7c73",
    "\u98df\u7528\u6cb9",
    "\u9762\u7c89",
    "\u53e3\u7f69",
    "\u77ff\u6cc9\u6c34",
    "\u5c0f\u96f6\u98df",
    "\u7eb8\u5dfe",
    "\u8336\u5305",
    "A4\u6253\u5370\u7eb8",
    "\u7b7e\u5b57\u7b14",
    "2B\u94c5\u7b14",
    "\u6a61\u76ae",
    "\u63d2\u7ebf\u677f",
    "\u7f51\u7ebf",
    "\u5907\u7528\u9f20\u6807",
    "\u5907\u7528\u952e\u76d8",
    "\u6fc0\u5149\u7b14",
    "5\u53f7\u7535\u6c60",
    "\u8ba1\u65f6\u5668",
    "\u7edd\u7f18\u80f6\u5e26",
    "\u624e\u5e26",
    "\u87ba\u4e1d\u5200\u5957\u88c5",
    "\u5907\u7528\u7535\u6c60\u5305",
    "\u73bb\u7247",
    "\u6d88\u6bd2\u9152\u7cbe",
    "\u85af\u7247",
)


def _purge_purchase_cascade(db: Session, order_prefix: str) -> None:
    from .models.purchase import Purchase, PurchaseItem
    from .models.delivery import Delivery
    from .models.stock import StockIn, StockOut
    from .models.trace import TraceRecord

    rows = db.query(Purchase).filter(Purchase.order_no.like(f"{order_prefix}%")).all()
    if not rows:
        return
    pids = [p.id for p in rows]
    db.query(Delivery).filter(Delivery.purchase_id.in_(pids)).delete(synchronize_session=False)
    db.query(StockOut).filter(StockOut.purchase_id.in_(pids)).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.purchase_id.in_(pids)).delete(synchronize_session=False)
    db.query(PurchaseItem).filter(PurchaseItem.purchase_id.in_(pids)).delete(synchronize_session=False)
    db.query(Purchase).filter(Purchase.id.in_(pids)).delete(synchronize_session=False)
    db.query(TraceRecord).filter(TraceRecord.batch_no.like(f"{order_prefix}%")).delete(synchronize_session=False)


def purge_legacy_noise(db: Session) -> None:
    """仅清理旧版 init/随机种子垃圾，不动 POCHAIN / DLVCHAIN / LOT 等当前预置主数据。"""
    from .models.trace import TraceRecord
    from .models.stock import StockIn, StockOut, Inventory
    from .models.delivery import Delivery
    from .models.audit_log import AuditLog

    _purge_purchase_cascade(db, "PO202603")

    db.query(TraceRecord).filter(TraceRecord.batch_no == "BATCH2024001").delete(synchronize_session=False)
    db.query(TraceRecord).filter(TraceRecord.batch_no.like("SN-DEMO-%")).delete(synchronize_session=False)

    db.query(StockIn).filter(StockIn.order_no.like("SI-DEMO%")).delete(synchronize_session=False)
    db.query(StockOut).filter(StockOut.order_no.like("SO-DEMO%")).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.order_no.in_(["IN001", "IN002"])).delete(synchronize_session=False)
    db.query(StockOut).filter(StockOut.order_no == "OUT001").delete(synchronize_session=False)

    db.query(Delivery).filter(Delivery.delivery_no.in_(["DLV001", "DLV002", "DLV003"])).delete(synchronize_session=False)
    db.query(Delivery).filter(Delivery.delivery_no.like("DLV202603%")).delete(synchronize_session=False)

    db.query(Inventory).filter(Inventory.batch_no.like("SN-DEMO-%")).delete(synchronize_session=False)

    db.query(AuditLog).filter(AuditLog.action == "_rich_seed_applied").delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.detail.contains("\u5907\u6ce8\u7b2c")).delete(synchronize_session=False)


def purge_cohesive_dataset(db: Session) -> None:
    """删除当前「完整链路」预置数据，供 --force 重建。"""
    from .models.trace import TraceRecord
    from .models.stock import StockIn, StockOut, Inventory
    from .models.audit_log import AuditLog as AuditLogModel

    _purge_purchase_cascade(db, "POCHAIN")
    _purge_purchase_cascade(db, "POHIST")
    db.query(TraceRecord).filter(TraceRecord.batch_no.like("DLVCHAIN%")).delete(synchronize_session=False)
    db.query(TraceRecord).filter(TraceRecord.batch_no.like("DLVHIST%")).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.order_no.like("IN-OPEN-%")).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.order_no.like("INCHAIN-BULK%")).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.order_no.like("SI-CHAIN-%")).delete(synchronize_session=False)
    db.query(StockIn).filter(StockIn.order_no.like("SI-HIST-%")).delete(synchronize_session=False)
    db.query(StockOut).filter(StockOut.order_no.like("OUT-CHAIN-%")).delete(synchronize_session=False)
    db.query(StockOut).filter(StockOut.order_no.like("OUT-HIST-%")).delete(synchronize_session=False)
    db.query(Inventory).filter(Inventory.batch_no.like("LOT-%")).delete(synchronize_session=False)
    db.query(AuditLogModel).filter(AuditLogModel.action == MARKER_ACTION).delete(synchronize_session=False)
    db.query(AuditLogModel).filter(
        or_(
            AuditLogModel.target_id.like("POCHAIN%"),
            AuditLogModel.target_id.like("POHIST%"),
            AuditLogModel.target_id.like("OUT-CHAIN-%"),
            AuditLogModel.target_id == "W-01",
        )
    ).delete(synchronize_session=False)


def _tr(
    db: Session,
    batch_no: str,
    stage: str,
    content: str,
    created_at: datetime,
) -> None:
    from .models.trace import TraceRecord

    r = TraceRecord(batch_no=batch_no, stage=stage, content=content[:256])
    r.created_at = created_at
    db.add(r)


def _audit(
    db: Session,
    user_name: str,
    user_role: str,
    action: str,
    target_type: str,
    target_id: str,
    detail: str,
    created_at: datetime,
    user_id: int | None = None,
) -> None:
    from .models.audit_log import AuditLog

    a = AuditLog(
        user_id=user_id,
        user_name=user_name,
        user_role=user_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail[:512],
    )
    a.created_at = created_at
    db.add(a)


def seed_cohesive_dataset(db: Session) -> None:
    from .models.user import User
    from .models.supplier import Supplier
    from .models.purchase import Purchase, PurchaseItem
    from .models.delivery import Delivery
    from .models.stock import StockIn, StockOut
    from .models.goods import Goods
    from .models.warning import Warning
    from .models.audit_log import AuditLog

    db.query(Warning).delete(synchronize_session=False)

    teachers = db.query(User).filter(User.role == "counselor_teacher").order_by(User.id.asc()).all()
    if not teachers:
        u = db.query(User).filter(User.username.in_(["counselor_teacher", "teacher1"])).order_by(User.id.asc()).first()
        teachers = [u] if u else []
    if not teachers:
        raise RuntimeError("Missing demo users: need at least one counselor_teacher")

    logistics = db.query(User).filter(User.username.in_(["logistics_admin", "system_admin", "admin"])).order_by(User.id.asc()).first()
    warehouse = db.query(User).filter(User.username == "warehouse_procurement").first()
    sup_xx = db.query(Supplier).filter(Supplier.name == "XX\u98df\u54c1\u6709\u9650\u516c\u53f8").first()
    sup_yy = db.query(Supplier).filter(Supplier.name == "YY\u7cae\u6cb9\u516c\u53f8").first()
    if not logistics:
        raise RuntimeError("Missing demo users: need logistics_admin")

    wh_name = (warehouse.real_name or warehouse.username) if warehouse else "\u4ed3\u50a8\u5458"
    lg_name = logistics.real_name or logistics.username
    teacher = teachers[0]
    tc_name = teacher.real_name or teacher.username
    sup_a_name = sup_xx.name if sup_xx else "\u4f9b\u5e94\u5546A"
    sup_b_name = sup_yy.name if sup_yy else "\u4f9b\u5e94\u5546B"

    anchor = datetime(2025, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
    rng = random.Random(7)

    goods_map = {g.name: g for g in db.query(Goods).filter(Goods.name.in_(DEMO_GOOD_NAMES)).all()}

    open_ts = anchor - timedelta(days=140)
    for nm in DEMO_GOOD_NAMES:
        if nm not in goods_map:
            continue
        g = goods_map[nm]
        qty = 900.0 + float((g.id or 0) % 120)
        si = StockIn(
            order_no=f"IN-OPEN-{g.id:03d}",
            goods_name=nm,
            quantity=qty,
            unit=g.unit or "\u4ef6",
            batch_no=f"LOT-OPEN-{g.id:03d}",
            purchase_id=None,
        )
        si.created_at = open_ts
        db.add(si)

    bulk_ins = [
        ("\u5927\u7c73", 120, "\u888b", "INCHAIN-BULK-001"),
        ("\u98df\u7528\u6cb9", 80, "\u6876", "INCHAIN-BULK-002"),
        ("\u77ff\u6cc9\u6c34", 600, "\u74f6", "INCHAIN-BULK-003"),
        ("A4\u6253\u5370\u7eb8", 200, "\u5305", "INCHAIN-BULK-004"),
        ("\u7b7e\u5b57\u7b14", 500, "\u652f", "INCHAIN-BULK-005"),
    ]
    for i, (name, qty, unit, oid) in enumerate(bulk_ins):
        si = StockIn(
            order_no=oid,
            goods_name=name,
            quantity=qty,
            unit=unit,
            batch_no=f"LOT-BULK-{i + 1:03d}",
            purchase_id=None,
        )
        si.created_at = anchor - timedelta(days=rng.randint(90, 130))
        db.add(si)

    chains: list[dict] = [
        {
            "order_no": "POCHAIN-20251108001",
            "status": "completed",
            "supplier": sup_xx,
            "dest": "\u56fe\u4e66\u9986\u62a5\u544a\u5385",
            "items": [("\u77ff\u6cc9\u6c34", 120.0, "\u74f6"), ("\u5c0f\u96f6\u98df", 60.0, "\u4efd")],
            "handoff": "HDA20251108001",
            "lot": "LOT-C01",
            "delivery_no": "DLVCHAIN-20251108001",
            "dstat": "received",
        },
        {
            "order_no": "POCHAIN-20251112002",
            "status": "delivering",
            "supplier": sup_xx,
            "dest": "\u4fe1\u606f\u697c\u673a\u623f",
            "items": [("\u5907\u7528\u9f20\u6807", 6.0, "\u4e2a")],
            "handoff": "HDD20251112002",
            "lot": "LOT-C02",
            "delivery_no": "DLVCHAIN-20251112002",
            "dstat": "on_way",
        },
        {
            "order_no": "POCHAIN-20251115003",
            "status": "stocked_out",
            "supplier": sup_yy,
            "dest": "\u5b9e\u8bad\u697cA201",
            "items": [("A4\u6253\u5370\u7eb8", 20.0, "\u5305"), ("\u7b7e\u5b57\u7b14", 40.0, "\u652f")],
            "handoff": "HDO20251115003",
            "lot": "LOT-C03",
            "delivery_no": "",
            "dstat": "",
        },
        {
            "order_no": "POCHAIN-20251118004",
            "status": "stocked_in",
            "supplier": sup_xx,
            "dest": "\u673a\u623fB203",
            "items": [("\u63d2\u7ebf\u677f", 10.0, "\u4e2a"), ("\u7f51\u7ebf", 12.0, "\u6839")],
            "handoff": "HDI20251118004",
            "lot": "LOT-C04",
            "delivery_no": "",
            "dstat": "",
        },
        {
            "order_no": "POCHAIN-20251120005",
            "status": "confirmed",
            "supplier": sup_yy,
            "dest": "\u98df\u5802\u540e\u52e4",
            "items": [("\u5927\u7c73", 15.0, "\u888b")],
            "handoff": "HDS20251120005",
            "lot": "LOT-C05",
            "delivery_no": "",
            "dstat": "",
        },
        {
            "order_no": "POCHAIN-20251122006",
            "status": "approved",
            "supplier": sup_xx,
            "dest": "\u533b\u52a1\u5ba4",
            "items": [("\u53e3\u7f69", 20.0, "\u76d2")],
            "handoff": "HDA20251122006",
            "lot": "LOT-C06",
            "delivery_no": "",
            "dstat": "",
        },
        {
            "order_no": "POCHAIN-20251125007",
            "status": "pending",
            "supplier": None,
            "dest": "\u884c\u653f\u697c\u4f1a\u8bae\u5ba4",
            "items": [("\u7eb8\u5dfe", 8.0, "\u76d2"), ("\u8336\u5305", 4.0, "\u76d2")],
            "handoff": "HDP20251125007",
            "lot": "LOT-C07",
            "delivery_no": "",
            "dstat": "",
        },
    ]

    for idx, ch in enumerate(chains):
        t0 = anchor + timedelta(days=idx * 2, hours=8)
        applicant = teachers[idx % len(teachers)]
        receiver_teacher = teachers[(idx + 2) % len(teachers)]
        receiver_name = receiver_teacher.real_name or receiver_teacher.username
        app_name = applicant.real_name or applicant.username

        p = Purchase(
            order_no=ch["order_no"],
            status=ch["status"],
            applicant_id=applicant.id,
            supplier_id=(ch["supplier"].id if ch["supplier"] else None),
            approved_by_id=logistics.id if ch["status"] != "pending" else None,
            destination=ch["dest"],
            receiver_name=receiver_name,
            handoff_code=ch["handoff"],
            completed_at=(t0 + timedelta(days=6) if ch["status"] == "completed" else None),
        )
        p.created_at = t0
        db.add(p)
        db.flush()
        for name, qty, unit in ch["items"]:
            db.add(PurchaseItem(purchase_id=p.id, goods_name=name, quantity=qty, unit=unit))

        st = ch["status"]
        sup_label = sup_a_name if ch["supplier"] == sup_xx else (sup_b_name if ch["supplier"] else "-")

        _tr(db, ch["order_no"], "\u7533\u8bf7", f"{app_name}\u63d0\u4ea4\u91c7\u8d2d\u7533\u8bf7\uff0c\u76ee\u7684\u5730={ch['dest']}\uff1b\u4ea4\u63a5\u7801={ch['handoff']}", t0)
        if st != "pending":
            _tr(
                db,
                ch["order_no"],
                "\u5ba1\u6279",
                f"{lg_name}\u5ba1\u6279\u901a\u8fc7\uff0c\u6307\u6d3e\u4f9b\u5e94\u5546={sup_label}\uff1b\u6279\u6b21\u6807\u8bc6={ch['lot']}",
                t0 + timedelta(hours=3),
            )
            _audit(
                db,
                lg_name,
                "logistics_admin",
                "purchase_approve",
                "purchase",
                ch["order_no"],
                f"\u5ba1\u6279\u901a\u8fc7\u5355\u636e {ch['order_no']}\uff0c\u4f9b\u5e94\u5546={sup_label}",
                t0 + timedelta(hours=3),
                logistics.id,
            )
        if st in ("confirmed", "stocked_in", "stocked_out", "delivering", "completed"):
            _tr(
                db,
                ch["order_no"],
                "\u4f9b\u5e94\u5546",
                f"{sup_label}\u5df2\u63a5\u5355\u5e76\u53d1\u8d27\uff0c\u5916\u5305\u88c5\u5b8c\u597d\uff1b\u6279\u6b21={ch['lot']}\uff1b\u9a7e\u9a76\u5458\u674e\u5e08\u5085",
                t0 + timedelta(hours=8),
            )
        if st in ("stocked_in", "stocked_out", "delivering", "completed"):
            suf = ch["order_no"][-5:]
            sin_list: list[str] = []
            for k, (name, qty, unit) in enumerate(ch["items"]):
                sin = f"SI-CHAIN-{suf}-{k:02d}"
                si = StockIn(
                    order_no=sin,
                    goods_name=name,
                    quantity=qty,
                    unit=unit,
                    batch_no=ch["lot"],
                    purchase_id=p.id,
                )
                si.created_at = t0 + timedelta(hours=14)
                db.add(si)
                sin_list.append(sin)
            sin_join = "\u3001".join(sin_list)
            _tr(
                db,
                ch["order_no"],
                "\u5165\u5e93",
                f"{wh_name}\u5b8c\u6210\u91c7\u8d2d\u5165\u5e93\uff0c\u5165\u5e93\u5355={sin_join}\uff0c\u6279\u6b21={ch['lot']}",
                t0 + timedelta(hours=14),
            )
            _audit(
                db,
                wh_name,
                "warehouse_procurement",
                "stock_in",
                "stock_in",
                sin_list[0],
                f"\u5173\u8054\u91c7\u8d2d\u5355 {ch['order_no']}\uff0c\u6279\u6b21={ch['lot']}",
                t0 + timedelta(hours=14),
                warehouse.id if warehouse else None,
            )
        if st in ("stocked_out", "delivering", "completed"):
            suf = ch["order_no"][-5:]
            sout_list: list[str] = []
            for k, (name, qty, unit) in enumerate(ch["items"]):
                sout = f"OUT-CHAIN-{suf}-{k:02d}"
                so = StockOut(
                    order_no=sout,
                    goods_name=name,
                    quantity=qty,
                    unit=unit,
                    batch_no=ch["lot"],
                    purchase_id=p.id,
                    destination=ch["dest"],
                    receiver_name=receiver_name,
                    handoff_code=ch["handoff"],
                )
                so.created_at = t0 + timedelta(hours=20)
                db.add(so)
                sout_list.append(sout)
            sout_join = "\u3001".join(sout_list)
            _tr(
                db,
                ch["order_no"],
                "\u51fa\u5e93",
                f"{wh_name}\u6309\u7533\u8bf7\u51fa\u5e93\uff0c\u51fa\u5e93\u5355={sout_join}\uff1b\u9886\u7528\u5355\u4f4d={ch['dest']}",
                t0 + timedelta(hours=20),
            )
        if st in ("delivering", "completed") and ch["delivery_no"]:
            d = Delivery(
                delivery_no=ch["delivery_no"],
                purchase_id=p.id,
                destination=ch["dest"],
                status=ch["dstat"],
                receiver_name=receiver_name,
                handoff_code=ch["handoff"],
                receiver_user_id=receiver_teacher.id,
                scheduled_at=t0 + timedelta(hours=22),
                actual_at=(t0 + timedelta(days=1) if ch["dstat"] == "received" else None),
            )
            d.created_at = t0 + timedelta(hours=22)
            db.add(d)
            _tr(
                db,
                ch["order_no"],
                "\u914d\u9001",
                f"\u914d\u9001\u5355{ch['delivery_no']}\u5df2\u53d1\u8f66\uff0c\u9a7e\u9a76\u5458\u738b\u5e08\u5085\uff0c\u76ee\u7684\u5730={ch['dest']}",
                t0 + timedelta(hours=22),
            )
            _tr(db, ch["delivery_no"], "\u914d\u9001", f"\u540c\u7a0b\u8ddf\u8e2a\u5355\u53f7={ch['delivery_no']}\uff0c\u4e0e\u91c7\u8d2d\u5355{ch['order_no']}\u5173\u8054", t0 + timedelta(hours=22))
        if st == "completed":
            _tr(
                db,
                ch["order_no"],
                "\u7b7e\u6536",
                f"{receiver_name}\u73b0\u573a\u9a8c\u6536\u7269\u8d44\u5e76\u786e\u8ba4\u4ea4\u63a5\u7801\uff0c\u95ed\u73af\u5b8c\u6210",
                t0 + timedelta(days=1, hours=4),
            )

    goods_units = {n: ((goods_map[n].unit if n in goods_map else None) or "\u4ef6") for n in DEMO_GOOD_NAMES}
    seed_random_purchase_orders(
        db,
        anchor=anchor,
        teachers=teachers,
        logistics=logistics,
        warehouse=warehouse,
        sup_xx=sup_xx,
        sup_yy=sup_yy,
        goods_names=list(DEMO_GOOD_NAMES),
        goods_units=goods_units,
        rng=random.Random(42),
        n_orders=24,
    )
    rebuild_inventory_from_ledger(db, DEMO_GOOD_NAMES)

    for w in [
        ("high", "\u5927\u7c73 25kg", "\u5e93\u5b58\u63a5\u8fd1\u5b66\u6821\u5f00\u5b66\u5b63\u7528\u7cae\u5cf0\u503c\uff0c\u5efa\u8bae\u4f18\u5148\u8865\u8d27"),
        ("medium", "\u5c0f\u96f6\u98df", "\u67d0\u6279\u6b21\u4fdd\u8d28\u671f\u5269\u4f59 45 \u5929\uff0c\u5efa\u8bae\u73ed\u4f1a\u6d3b\u52a8\u4f18\u5148\u6d88\u5316"),
        ("medium", "A4\u6253\u5370\u7eb8", "\u7ade\u8d5b\u5468\u671f\u95f4\u6253\u5370\u91cf\u4e0a\u5347\uff0c\u5df2\u540c\u6b65\u540e\u52e4\u52a0\u5355"),
        ("low", "\u8336\u5305", "\u5e93\u5b58\u6b63\u5e38\uff0c\u5b9a\u671f\u8d28\u68c0\u8bb0\u5f55\u5df2\u5f52\u6863"),
        ("high", "\u63d2\u7ebf\u677f", "\u5b89\u5168\u7ea7\u522b\u9ad8\uff0c\u51fa\u5e93\u9700\u53cc\u4eba\u590d\u6838\u5df2\u542f\u7528"),
    ]:
        db.add(Warning(level=w[0], material=w[1], description=w[2], status="pending"))

    narrative_audits = [
        (tc_name, "counselor_teacher", "purchase_create", "purchase", "POCHAIN-20251125007", "\u63d0\u4ea4\u8336\u6b47\u7eb8\u5dfe\u8865\u8d27\u7533\u8bf7\uff0c\u9644\u73ed\u7ea7\u4eba\u6570\u8bf4\u660e\u3002"),
        (lg_name, "logistics_admin", "supplier_ship", "purchase", "POCHAIN-20251108001", "\u4f9b\u5e94\u5546\u5df2\u4e0a\u4f20\u51fa\u5382\u68c0\u9a8c\u62a5\u544a\uff08PDF\uff09\u3002"),
        (wh_name, "warehouse_procurement", "stock_out", "stock_out", "OUT-CHAIN-08001-00", "\u6309\u7533\u8bf7\u51fa\u5e93\u81f3\u56fe\u4e66\u9986\uff0c\u4ea4\u63a5\u7801\u6838\u5bf9\u65e0\u8bef\u3002"),
        ("\u7ba1\u7406\u5458", "system_admin", "warning_handle", "warning", "W-01", "\u5df2\u901a\u77e5\u4ed3\u50a8\u52a0\u7d27\u5927\u7c73\u8865\u8d27\u5e76\u7559\u75d5\u5ba1\u8ba1\u3002"),
    ]
    for i, (un, role, act, tt, tid, det) in enumerate(narrative_audits):
        _audit(db, un, role, act, tt, tid, det, anchor + timedelta(days=3, hours=i), None)

    db.add(
        AuditLog(
            user_id=None,
            user_name="\u7cfb\u7edf",
            user_role="system",
            action=MARKER_ACTION,
            target_type="seed",
            target_id=MARKER_TARGET,
            detail="Cohesive demo: POCHAIN+POHIST, ledger-rebuilt inventory, trace, delivery, warnings.",
        )
    )


def apply_cohesive_demo(db: Session, *, force: bool = False) -> bool:
    """Return True if dataset was (re)written."""
    from .models.audit_log import AuditLog

    purge_legacy_noise(db)
    if force:
        purge_cohesive_dataset(db)

    exists = (
        db.query(AuditLog)
        .filter(AuditLog.action == MARKER_ACTION, AuditLog.target_id == MARKER_TARGET)
        .first()
    )
    if exists and not force:
        db.flush()
        return False

    seed_cohesive_dataset(db)
    return True


if __name__ == "__main__":
    import argparse
    from .database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Remove POCHAIN and re-insert cohesive demo")
    args = ap.parse_args()
    session = SessionLocal()
    try:
        changed = apply_cohesive_demo(session, force=args.force)
        session.commit()
        print("Cohesive demo applied." if changed else "Already present; use --force to rebuild.")
    finally:
        session.close()
