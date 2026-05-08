from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt
from jwt import PyJWTError as JWTError
from database import get_db
import os

SECRET_KEY = os.getenv("SECRET_KEY", "sabitrack_default_secret_change_in_production")
ALGORITHM  = "HS256"
EXPIRE_DAYS = 30

security = HTTPBearer()

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    from models import User
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, detail="Невалидный токен")
    except JWTError:
        raise HTTPException(401, detail="Невалидный или истёкший токен")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, detail="Пользователь не найден")
import jwt
from jwt import PyJWTError as JWTError
# Убедитесь, что settings у вас импортирован, если вы его используете
# from config import settings 

async def decode_token(token: str):
    try:
        # Расшифровываем токен. 
        # ВНИМАНИЕ: замените settings.SECRET_KEY на вашу переменную, если она называется иначе
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None





    
    return user
