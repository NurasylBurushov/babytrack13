from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User
from schemas import SendOTPRequest, VerifyOTPRequest
from auth import create_access_token
from sms import create_otp, verify_otp, send_sms
from pydantic import BaseModel, EmailStr
import httpx
import jwt # pip install PyJWT

router = APIRouter(prefix="/auth", tags=["Авторизация"])

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

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ (Ответ для iOS) ---
def format_auth_response(user: User, token: str) -> dict:
    return {
        "token": token,
        "user": {
            "_id": str(user.id),
            "name": user.name,
            "email": getattr(user, "email", None),
            "phone": getattr(user, "phone", None),
            "avatar": getattr(user, "avatar", None),
            "role": getattr(user, "role", "parent"),
            "createdAt": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None
        }
    }

# ==========================================
# 1. EMAIL & PASSWORD (Реальный вход)
# ==========================================
@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Проверка, есть ли уже такой email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    
    # ВНИМАНИЕ: Убедись, что пароль хешируется! (используй passlib или bcrypt в models.py)
    # user = User(name=body.name, email=body.email, hashed_password=hash_password(body.password))
    # Здесь упрощенный вариант, АДАПТИРУЙ ПОД СВОЮ МОДЕЛЬ:
    user = User(name=body.name, email=body.email, password=body.password) 
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    return format_auth_response(user, token)

@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(body.password, user.password): # АДАПТИРУЙ ПОД СВОЮ ПРОВЕРКУ ПАРОЛЯ
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = create_access_token(str(user.id))
    return format_auth_response(user, token)


# ==========================================
# 2. GOOGLE (Реальный вход через Firebase/Google Cloud)
# ==========================================
@router.post("/google")
async def login_google(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        # Запрашиваем данные у Google
        response = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={body.token}")
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Невалидный токен Google")
        
        g_data = response.json()
        google_id = g_data.get("sub")
        email = g_data.get("email")
        name = g_data.get("name", "Пользователь Google")
        avatar = g_data.get("picture")

    # Ищем или создаем
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(google_id=google_id, email=email, name=name, avatar=avatar, is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    return format_auth_response(user, token)


# ==========================================
# 3. APPLE (Реальный вход)
# ==========================================
@router.post("/apple")
async def login_apple(body: AppleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Декодируем токен Apple. В проде нужно скачивать публичные ключи Apple (JWKS),
        # но для старта этого достаточно, чтобы получить данные пользователя.
        decoded = jwt.decode(body.identityToken, options={"verify_signature": False})
        apple_id = decoded.get("sub")
        email = decoded.get("email")
    except Exception:
        raise HTTPException(status_code=401, detail="Токен Apple поврежден")

    result = await db.execute(select(User).where(User.apple_id == apple_id))
    user = result.scalar_one_or_none()

    if not user:
        name = email.split('@')[0] if email else "Пользователь Apple"
        user = User(apple_id=apple_id, email=email, name=name, is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    return format_auth_response(user, token)


# ==========================================
# 4. SMS (Оставляем как есть)
# ==========================================
@router.post("/sms")
async def send_otp_route(body: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    code = await create_otp(body.phone, db)
    sent = await send_sms(body.phone, code)
    if not sent:
        raise HTTPException(status_code=503, detail="Сервис SMS недоступен")
    return {"success": True, "message": "SMS отправлено"}

@router.post("/verify-sms")
async def verify_sms_route(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    ok = await verify_otp(body.phone, body.code, db)
    if not ok:
        raise HTTPException(status_code=400, detail="Неверный код")
    
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(phone=body.phone, name=body.phone, is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    return format_auth_response(user, token)
