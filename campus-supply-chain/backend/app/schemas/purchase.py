from pydantic import BaseModel
from datetime import datetime


class PurchaseItemCreate(BaseModel):
    goods_name: str
    quantity: float
    unit: str = ""


class PurchaseCreate(BaseModel):
    items: list[PurchaseItemCreate]


class PurchaseItemResponse(BaseModel):
    id: int
    goods_name: str
    quantity: float
    unit: str

    class Config:
        from_attributes = True


class PurchaseResponse(BaseModel):
    id: int
    order_no: str
    status: str
    created_at: datetime | None = None
    items: list[PurchaseItemResponse] = []

    class Config:
        from_attributes = True
