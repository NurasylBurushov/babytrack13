from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User
from schemas import SendOTPRequest, VerifyOTPRequest
from auth import create_access_token
from sms import create_otp, verify_otp, send_sms
from pydantic import BaseModel, EmailStr
import httpx
import jwt
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Авторизация"])

# Хэширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# --- СХЕМЫ ---
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    token: str

class AppleAuthRequest(BaseModel):
    identityToken: str

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ---
def format_auth_response(user: User, token: str) -> dict:
    return {
        "token": token,
        "user": {
            "_id": str(user.id),
            "name": user.name or "",
            "email": getattr(user, "email", None),
            "phone": getattr(user, "phone", None),
            "avatar": getattr(user, "avatar", None) or getattr(user, "avatar_url", None),
            "role": getattr(user, "role", "parent"),
            "createdAt": user.created_at.isoformat() if user.created_at else None
        }
    }

# ==========================================
# 1. SMS (основной метод для Казахстана)
# ==========================================
@router.post("/sms")
async def send_otp_route(body: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    try:
        code = await create_otp(body.phone, db)
        sent = await send_sms(body.phone, code)
        if not sent:
            raise HTTPException(status_code=503, detail="Сервис SMS недоступен. Проверьте SMSC_LOGIN и SMSC_PASSWORD")
        return {"success": True, "message": "SMS отправлено"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

@router.post("/verify-sms")
async def verify_sms_route(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    try:
        ok = await verify_otp(body.phone, body.code, db)
        if not ok:
            raise HTTPException(status_code=400, detail="Неверный или истёкший код")

        result = await db.execute(select(User).where(User.phone == body.phone))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                phone=body.phone,
                name=f"Пользователь {body.phone[-4:]}",
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = create_access_token(str(user.id))
        return format_auth_response(user, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")

# ==========================================
# 2. EMAIL & PASSWORD
# ==========================================
@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")

        if len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Пароль минимум 6 символов")

        user = User(
            name=body.name,
            email=body.email,
            password=hash_password(body.password),
            is_verified=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(str(user.id))
        return format_auth_response(user, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка регистрации: {str(e)}")

@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        if not user or not user.password:
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        if not verify_password(body.password, user.password):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")

        token = create_access_token(str(user.id))
        return format_auth_response(user, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка входа: {str(e)}")

# ==========================================
# 3. GOOGLE
# ==========================================
@router.post("/google")
async def login_google(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={body.token}"
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Невалидный токен Google")

            g_data = response.json()

        google_id = g_data.get("sub")
        email = g_data.get("email")
        name = g_data.get("name") or g_data.get("given_name") or (email.split("@")[0] if email else "Пользователь")
        avatar = g_data.get("picture")

        if not google_id:
            raise HTTPException(status_code=401, detail="Не удалось получить данные Google")

        # Ищем по google_id
        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if not user and email:
            # Ищем по email
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.google_id = google_id
                if avatar:
                    user.avatar = avatar
                await db.commit()
                await db.refresh(user)

        if not user:
            user = User(
                google_id=google_id,
                email=email,
                name=name,
                avatar=avatar,
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = create_access_token(str(user.id))
        return format_auth_response(user, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Google входа: {str(e)}")

# ==========================================
# 4. APPLE
# ==========================================
@router.post("/apple")
async def login_apple(body: AppleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        decoded = jwt.decode(
            body.identityToken,
            options={"verify_signature": False}
        )
        apple_id = decoded.get("sub")
        email = decoded.get("email")

        if not apple_id:
            raise HTTPException(status_code=401, detail="Токен Apple поврежден")

        result = await db.execute(select(User).where(User.apple_id == apple_id))
        user = result.scalar_one_or_none()

        if not user and email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.apple_id = apple_id
                await db.commit()
                await db.refresh(user)

        if not user:
            name = email.split("@")[0] if email else "Пользователь Apple"
            user = User(
                apple_id=apple_id,
                email=email,
                name=name,
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        token = create_access_token(str(user.id))
        return format_auth_response(user, token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка Apple входа: {str(e)}")
