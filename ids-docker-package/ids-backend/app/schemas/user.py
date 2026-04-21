from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    real_name: str = ""
    role: str
    department: str | None = None
    phone: str | None = None


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
