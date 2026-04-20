"""Replay StockIn / StockOut into Inventory — same rules as runtime API (FIFO out)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from ..api.stock import _sync_inventory_add, _sync_inventory_sub
from ..models.goods import Goods
from ..models.stock import Inventory, StockIn, StockOut


def _ts_utc(dt: datetime | None, epoch: datetime) -> datetime:
    if dt is None:
        return epoch
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rebuild_inventory_from_ledger(db: Session, goods_names: Iterable[str]) -> None:
    """
    Clear inventory rows for listed goods, then replay all stock_in / stock_out
    for those goods in chronological order so 库存查询 matches 出入库记录.
    """
    names = tuple(goods_names)
    if not names:
        return

    db.query(Inventory).filter(Inventory.goods_name.in_(names)).delete(synchronize_session=False)
    db.flush()

    goods_map = {g.name: g for g in db.query(Goods).filter(Goods.name.in_(names)).all()}

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    events: list[tuple[datetime, int, int, str, StockIn | StockOut]] = []
    for si in db.query(StockIn).filter(StockIn.goods_name.in_(names)).order_by(StockIn.id.asc()).all():
        ts = _ts_utc(si.created_at, epoch)
        events.append((ts, si.id, 0, "in", si))
    for so in db.query(StockOut).filter(StockOut.goods_name.in_(names)).order_by(StockOut.id.asc()).all():
        ts = _ts_utc(so.created_at, epoch)
        events.append((ts, so.id, 1, "out", so))

    # Same timestamp: process inbound before outbound (stable demo replay).
    events.sort(key=lambda x: (x[0], x[2], x[1]))

    shortfalls: list[str] = []
    for _ts, _eid, _prio, typ, row in events:
        if typ == "in":
            g = goods_map.get(row.goods_name)
            cat = g.category if g else ""
            _sync_inventory_add(
                db,
                row.goods_name,
                float(row.quantity or 0),
                row.unit or "\u4ef6",
                row.batch_no or "",
                cat,
            )
        else:
            res = _sync_inventory_sub(db, row.goods_name, float(row.quantity or 0))
            if not res["ok"]:
                shortfalls.append(f"{row.goods_name}: {row.order_no} {res['detail']}")
        # Session uses autoflush=False; sub/add must see prior rows.
        db.flush()

    db.flush()
    if shortfalls:
        # Demo seed should stay consistent; log once for operators
        import logging

        logging.getLogger(__name__).warning(
            "inventory_ledger replay shortfall (qty adjusted to 0 for those lines): %s",
            "; ".join(shortfalls[:12]),
        )
