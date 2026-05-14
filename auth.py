from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from jwt import PyJWTError as JWTError

from database import get_db
from config import get_settings

security = HTTPBearer(auto_error=True)

settings = get_settings()

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
EXPIRE_DAYS = 30


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """JWT в заголовке Authorization: Bearer …; в БД users.id — UUID."""
    from models import User

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Невалидный или истёкший токен")

    raw_sub = payload.get("sub")
    if raw_sub is None or raw_sub == "":
        raise HTTPException(status_code=401, detail="Невалидный токен")

    try:
        user_uuid = UUID(str(raw_sub))
    except ValueError:
        raise HTTPException(status_code=401, detail="Невалидный идентификатор в токене")

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user


def decode_token(token: str) -> str | None:
    """Возвращает user id из claim `sub` или None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub is not None else None
    except JWTError:
        return None