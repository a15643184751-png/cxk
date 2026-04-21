from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from ..config import settings


def verify_password(plain: str, hashed: str) -> bool:
    pw_bytes = plain.encode("utf-8")
    h_bytes = hashed.encode("utf-8") if isinstance(hashed, str) else hashed
    return bcrypt.checkpw(pw_bytes, h_bytes)


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
