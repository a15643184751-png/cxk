from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..core.security import create_access_token, get_password_hash, verify_password
from ..database import get_db
from ..models.user import User
from ..schemas.user import LoginRequest, UserCreate
from .deps import get_current_user, has_role, normalize_role

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    username = (data.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    candidates = [username]
    if username == settings.IDS_DEFAULT_ADMIN_USERNAME:
        candidates.extend(["system_admin", "admin"])

    user = None
    for candidate in candidates:
        row = db.query(User).filter(User.username == candidate).first()
        if row and verify_password(data.password, row.hashed_password):
            user = row
            break

    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name or user.username,
            "role": normalize_role(user.role),
            "department": user.department,
            "phone": user.phone,
        },
    }


@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name or current_user.username,
        "role": normalize_role(current_user.role),
        "department": current_user.department,
        "phone": current_user.phone,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_role(current_user, "ids_admin"):
        raise HTTPException(status_code=403, detail="仅 IDS 管理员可查看用户列表")

    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": row.id,
            "username": row.username,
            "real_name": row.real_name or row.username,
            "role": normalize_role(row.role),
            "department": row.department,
            "phone": row.phone,
        }
        for row in users
    ]


@router.post("/users")
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not has_role(current_user, "ids_admin"):
        raise HTTPException(status_code=403, detail="仅 IDS 管理员可新增用户")

    username = (data.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=username,
        hashed_password=get_password_hash(data.password),
        real_name=(data.real_name or "").strip() or username,
        role=normalize_role(data.role),
        department=(data.department or "").strip(),
        phone=(data.phone or "").strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "role": normalize_role(user.role),
        "department": user.department,
        "phone": user.phone,
    }
