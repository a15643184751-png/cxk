"""Random historical purchases POHIST-* with trace + stock movements (ledger replay builds inventory)."""
from __future__ import annotations

import random
from datetime import timedelta
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .models.user import User
from .models.supplier import Supplier
from .models.purchase import Purchase, PurchaseItem
from .models.delivery import Delivery
from .models.stock import StockIn, StockOut


def _tr(db: Session, batch_no: str, stage: str, content: str, created_at: datetime) -> None:
    from .models.trace import TraceRecord

    r = TraceRecord(batch_no=batch_no, stage=stage, content=content[:256])
    r.created_at = created_at
    db.add(r)


DESTINATIONS = (
    "\u56fe\u4e66\u9986\u62a5\u544a\u5385",
    "302\u5b9e\u9a8c\u5ba4",
    "\u884c\u653f\u697c\u4f1a\u8bae\u5ba4",
    "\u4f53\u80b2\u9986\u4e3b\u573a",
    "\u5b66\u751f\u5bbf\u820d\u533a",
    "\u533b\u52a1\u5ba4",
    "\u98df\u5802\u4e8c\u697c",
    "\u5b9e\u8bad\u697cB103",
    "\u827a\u672f\u4e2d\u5fc3\u526f\u5385",
    "\u673a\u623f\u76d1\u63a7\u4e2d\u5fc3",
)


def seed_random_purchase_orders(
    db: Session,
    *,
    anchor: datetime,
    teachers: list[User],
    logistics: User,
    warehouse: User | None,
    sup_xx: Supplier | None,
    sup_yy: Supplier | None,
    goods_names: list[str],
    goods_units: dict[str, str],
    rng: random.Random,
    n_orders: int = 24,
) -> None:
    if len(teachers) < 1 or not goods_names:
        return
    from .models.trace import TraceRecord

    # 幂等重建：避免重复种子导致 POHIST/DLVHIST 轨迹叠加
    db.query(TraceRecord).filter(TraceRecord.batch_no.like("POHIST-%")).delete(synchronize_session=False)
    db.query(TraceRecord).filter(TraceRecord.batch_no.like("DLVHIST-%")).delete(synchronize_session=False)

    lg_name = logistics.real_name or logistics.username
    wh_name = (warehouse.real_name or warehouse.username) if warehouse else "\u4ed3\u50a8\u5458"
    sups = [s for s in (sup_xx, sup_yy) if s]
    sup_labels = {s.id: s.name for s in sups}

    statuses = [
        "completed",
        "delivering",
        "stocked_out",
        "stocked_in",
        "shipped",
        "confirmed",
        "approved",
        "pending",
        "rejected",
    ]
    weights = [9, 2, 3, 3, 2, 3, 5, 4, 3]

    base_seq = 80000

    for i in range(n_orders):
        st = rng.choices(statuses, weights=weights, k=1)[0]
        # Start after fixed POCHAIN demo window so ledger replay keeps chain outs satisfiable.
        t0 = anchor + timedelta(
            days=rng.randint(12, 88),
            hours=rng.randint(7, 20),
            minutes=rng.randint(0, 59),
        )
        seq = base_seq + i
        order_no = f"POHIST-{seq}"
        applicant = teachers[rng.randint(0, len(teachers) - 1)]
        receiver_u = teachers[rng.randint(0, len(teachers) - 1)]
        receiver_name = receiver_u.real_name or receiver_u.username
        dest = DESTINATIONS[rng.randint(0, len(DESTINATIONS) - 1)]
        handoff = f"HDP{seq % 100000}"

        n_it = rng.randint(1, min(3, len(goods_names)))
        picked = rng.sample(goods_names, n_it)
        items: list[tuple[str, float, str]] = []
        for pn in picked:
            unit = goods_units.get(pn) or "\u4ef6"
            if unit in ("\u74f6", "\u652f", "\u6839", "\u8282", "\u5757"):
                q = float(rng.randint(12, 120))
            elif unit in ("\u888b", "\u5305", "\u76d2"):
                q = float(rng.randint(3, 40))
            else:
                q = float(rng.randint(8, 80))
            items.append((pn, q, unit))

        sup = None
        if st not in ("pending", "rejected") and sups:
            sup = sups[rng.randint(0, len(sups) - 1)]

        p = Purchase(
            order_no=order_no,
            status=st,
            applicant_id=applicant.id,
            supplier_id=sup.id if sup else None,
            approved_by_id=logistics.id if st not in ("pending", "rejected") else None,
            destination=dest,
            receiver_name=receiver_name,
            handoff_code=handoff,
            completed_at=(t0 + timedelta(days=5) if st == "completed" else None),
        )
        p.created_at = t0
        db.add(p)
        db.flush()

        for name, qty, unit in items:
            db.add(PurchaseItem(purchase_id=p.id, goods_name=name, quantity=qty, unit=unit))

        ap_name = applicant.real_name or applicant.username
        sup_lbl = sup_labels.get(sup.id, "\u4f9b\u5e94\u5546") if sup else "-"
        lot = f"LOT-H{seq}"

        _tr(db, order_no, "\u7533\u8bf7", f"{ap_name}\u63d0\u4ea4\u7533\u8bf7\uff0c\u6536\u8d27\u4eba={receiver_name}\uff1b\u5730\u70b9={dest}\uff1b\u7801={handoff}", t0)

        if st == "rejected":
            _tr(
                db,
                order_no,
                "\u5ba1\u6279",
                f"{lg_name}\u9a73\u56de\uff1a\u6570\u91cf/\u7528\u9014\u9700\u8fdb\u4e00\u6b65\u8bf4\u660e\uff1b\u5355\u53f7={order_no}",
                t0 + timedelta(hours=2),
            )
            continue

        if st != "pending":
            _tr(
                db,
                order_no,
                "\u5ba1\u6279",
                f"{lg_name}\u5ba1\u6279\u901a\u8fc7\uff0c\u4f9b\u5e94\u5546={sup_lbl}\uff1b\u6279\u6b21={lot}",
                t0 + timedelta(hours=2, minutes=rng.randint(5, 55)),
            )

        if st in ("confirmed", "shipped", "stocked_in", "stocked_out", "delivering", "completed"):
            _tr(
                db,
                order_no,
                "\u4f9b\u5e94\u5546",
                f"{sup_lbl}\u63a5\u5355\u5e76\u5b8c\u6210\u5907\u8d27/\u53d1\u8d27\u51c6\u5907\uff1b\u6279\u6b21={lot}",
                t0 + timedelta(hours=6),
            )

        if st == "shipped":
            _tr(
                db,
                order_no,
                "\u4f9b\u5e94\u5546",
                f"\u7269\u6d41\u5df2\u53d1\u8d27\uff0c\u6b63\u9a76\u5411\u6821\u56ed\u4ed3\u50a8\u70b9\uff1b\u6279\u6b21={lot}",
                t0 + timedelta(hours=10),
            )
            continue

        if st in ("stocked_in", "stocked_out", "delivering", "completed"):
            for k, (name, qty, unit) in enumerate(items):
                oid_si = f"SI-HIST-{seq}-{k + 1}"
                si = StockIn(
                    order_no=oid_si,
                    goods_name=name,
                    quantity=qty,
                    unit=unit,
                    batch_no=f"{lot}-{k + 1}",
                    purchase_id=p.id,
                )
                si.created_at = t0 + timedelta(hours=12 + k)
                db.add(si)
            _tr(
                db,
                order_no,
                "\u5165\u5e93",
                f"{wh_name}\u5b8c\u6210\u5165\u5e93\uff0c\u5171{len(items)}\u6761\u660e\u7ec6\uff1b\u6279\u6b21={lot}",
                t0 + timedelta(hours=13),
            )

        if st in ("stocked_out", "delivering", "completed"):
            for k, (name, qty, unit) in enumerate(items):
                oid_so = f"OUT-HIST-{seq}-{k + 1}"
                so = StockOut(
                    order_no=oid_so,
                    goods_name=name,
                    quantity=qty,
                    unit=unit,
                    batch_no=f"{lot}-{k + 1}",
                    purchase_id=p.id,
                    destination=dest,
                    receiver_name=receiver_name,
                    handoff_code=handoff,
                )
                so.created_at = t0 + timedelta(hours=18 + k)
                db.add(so)
            _tr(
                db,
                order_no,
                "\u51fa\u5e93",
                f"{wh_name}\u6309\u7533\u8bf7\u51fa\u5e93\uff0c\u76ee\u7684\u5730={dest}",
                t0 + timedelta(hours=19),
            )

        if st in ("delivering", "completed"):
            dno = f"DLVHIST-{seq}"
            dstat = "received" if st == "completed" else "on_way"
            d = Delivery(
                delivery_no=dno,
                purchase_id=p.id,
                destination=dest,
                status=dstat,
                receiver_name=receiver_name,
                handoff_code=handoff,
                receiver_user_id=receiver_u.id,
                scheduled_at=t0 + timedelta(hours=21),
                actual_at=(t0 + timedelta(days=1) if dstat == "received" else None),
            )
            d.created_at = t0 + timedelta(hours=21)
            db.add(d)
            _tr(db, order_no, "\u914d\u9001", f"\u914d\u9001\u5355{dno}\u5df2\u53d1\u8f66", t0 + timedelta(hours=21))
            _tr(db, dno, "\u914d\u9001", f"\u5173\u8054\u91c7\u8d2d\u5355{order_no}", t0 + timedelta(hours=21))

        if st == "completed":
            _tr(
                db,
                order_no,
                "\u7b7e\u6536",
                f"{receiver_name}\u73b0\u573a\u7b7e\u6536\uff0c\u95ed\u73af\u5b8c\u6210",
                t0 + timedelta(days=1, hours=3),
            )
