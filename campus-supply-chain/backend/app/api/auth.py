from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.user import User
from ..schemas.user import LoginRequest, LoginResponse, UserResponse, UserCreate
from ..core.security import verify_password, create_access_token, get_password_hash
from .deps import get_current_user, has_role, normalize_role

router = APIRouter(prefix="/user", tags=["auth"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    username = (data.username or "").strip()
    candidates = [username]
    # 兼容历史账号：system_admin <-> admin
    if username == "system_admin":
        candidates.append("admin")
    elif username == "admin":
        candidates.append("system_admin")

    user = None
    for uname in candidates:
        u = db.query(User).filter(User.username == uname).first()
        if u and verify_password(data.password, u.hashed_password):
            user = u
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


@router.get("/manage")
def list_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_role(current_user, "system_admin"):
        return []
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name or u.username,
            "role": normalize_role(u.role),
            "department": (u.department or "").strip(),
            "phone": (u.phone or "").strip(),
        }
        for u in users
    ]


@router.post("/manage")
def create_user(data: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_role(current_user, "system_admin"):
        raise HTTPException(status_code=403, detail="仅管理员可添加用户")
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
        "department": (user.department or "").strip(),
        "phone": (user.phone or "").strip(),
    }
