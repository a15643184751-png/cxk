from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.goods import Goods
from ..models.user import User
from ..schemas.goods import GoodsCreate, GoodsUpdate, GoodsResponse
from .deps import get_current_user, require_roles

router = APIRouter(prefix="/goods", tags=["goods"])
_view_allowed = require_roles("logistics_admin", "warehouse_procurement", "counselor_teacher")
_manage_allowed = require_roles("logistics_admin", "warehouse_procurement")


@router.get("", response_model=list[GoodsResponse])
def list_goods(
    keyword: str | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(_view_allowed),
):
    q = db.query(Goods)
    if keyword:
        q = q.filter(Goods.name.contains(keyword))
    if category:
        q = q.filter(Goods.category == category)
    return q.all()


@router.post("", response_model=GoodsResponse)
def create_goods(data: GoodsCreate, db: Session = Depends(get_db), current_user: User = Depends(_manage_allowed)):
    g = Goods(**data.model_dump())
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


@router.get("/{goods_id}", response_model=GoodsResponse)
def get_goods(goods_id: int, db: Session = Depends(get_db), current_user: User = Depends(_view_allowed)):
    g = db.query(Goods).filter(Goods.id == goods_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="物资不存在")
    return g


@router.put("/{goods_id}", response_model=GoodsResponse)
def update_goods(
    goods_id: int,
    data: GoodsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_manage_allowed),
):
    g = db.query(Goods).filter(Goods.id == goods_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="物资不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(g, k, v)
    db.commit()
    db.refresh(g)
    return g


@router.delete("/{goods_id}")
def delete_goods(goods_id: int, db: Session = Depends(get_db), current_user: User = Depends(_manage_allowed)):
    g = db.query(Goods).filter(Goods.id == goods_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="物资不存在")
    db.delete(g)
    db.commit()
    return {"code": 200, "message": "ok"}
