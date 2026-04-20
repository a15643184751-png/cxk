from pydantic import BaseModel


class GoodsBase(BaseModel):
    name: str
    category: str = ""
    spec: str = ""
    unit: str = ""
    safety_level: str = "medium"
    shelf_life_days: int = 365


class GoodsCreate(GoodsBase):
    pass


class GoodsUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    spec: str | None = None
    unit: str | None = None
    safety_level: str | None = None
    shelf_life_days: int | None = None


class GoodsResponse(GoodsBase):
    id: int

    class Config:
        from_attributes = True
