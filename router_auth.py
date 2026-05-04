from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, OTPCode
from auth import create_access_token
from pydantic import BaseModel, EmailStr
import httpx
import jwt
import re
import random
import string
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Авторизация"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helpers ───────────────────────────────────────────────
def hash_password(p: str) -> str:
    return pwd_context.hash(p)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("7"):
        return "+" + digits
    if len(digits) == 10:
        return "+7" + digits
    raise ValueError("Неверный формат номера")

def format_user(user: User, token: str) -> dict:
    return {
        "token": token,
        "user": {
            "_id":       str(user.id),
            "name":      user.name or "",
            "email":     user.email,
            "phone":     user.phone,
            "avatar":    user.avatar,
            "role":      user.role or "parent",
            "createdAt": user.created_at.isoformat() if user.created_at else None,
        }
    }

async def send_sms(phone: str, code: str) -> bool:
    import os, httpx
    login    = os.getenv("SMSC_LOGIN")
    password = os.getenv("SMSC_PASSWORD")

    if not login or not password:
        print(f"⚠️ SMS в DEV режиме. Код для {phone}: {code}")
        return True

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post("https://smsc.kz/sys/send.php", data={
                "login":   login,
                "psw":     password,
                "phones":  phone,
                "mes":     f"Ваш код SabiTrack: {code}",
                "charset": "utf-8",
            })
            print(f"📨 SMSC ответ: {r.text}")
            return "OK" in r.text or "ok" in r.text.lower()
    except Exception as e:
        print(f"❌ SMS ошибка: {e}")
        return False


# ── Schemas ───────────────────────────────────────────────
class SMSRequest(BaseModel):
    phone: str

class VerifySMSRequest(BaseModel):
    phone: str
    code: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class GoogleRequest(BaseModel):
    token: str

class AppleRequest(BaseModel):
    identityToken: str
    fullName: dict | None = None


# ══════════════════════════════════════════════════════════
# 1. SMS
# ══════════════════════════════════════════════════════════
@router.post("/sms")
async def send_otp(body: SMSRequest, db: AsyncSession = Depends(get_db)):
    try:
        phone = normalize_phone(body.phone)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    # Удаляем старые коды
    old = await db.execute(select(OTPCode).where(OTPCode.phone == phone))
    for otp in old.scalars().all():
        await db.delete(otp)

    code = "".join(random.choices(string.digits, k=4))
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)

    db.add(OTPCode(phone=phone, code=code, expires_at=expires))
    await db.commit()

    sent = await send_sms(phone, code)
    if not sent:
        raise HTTPException(503, detail="Не удалось отправить SMS")

    return {"success": True, "message": "SMS отправлено"}


@router.post("/verify-sms")
async def verify_otp(body: VerifySMSRequest, db: AsyncSession = Depends(get_db)):
    try:
        phone = normalize_phone(body.phone)
    except ValueError:
        raise HTTPException(400, detail="Неверный номер телефона")

    result = await db.execute(
        select(OTPCode).where(OTPCode.phone == phone, OTPCode.is_used == False)
        .order_by(OTPCode.created_at.desc())
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(400, detail="Код не найден. Запросите новый")

    if otp.attempts >= 5:
        raise HTTPException(400, detail="Слишком много попыток. Запросите новый код")

    if datetime.now(timezone.utc) > otp.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(400, detail="Код истёк. Запросите новый")

    if otp.code != body.code:
        otp.attempts += 1
        await db.commit()
        raise HTTPException(400, detail=f"Неверный код. Осталось попыток: {5 - otp.attempts}")

    otp.is_used = True
    await db.commit()

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if not user:
        user = User(phone=phone, name=f"Пользователь {phone[-4:]}", is_verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return format_user(user, create_access_token(str(user.id)))


# ══════════════════════════════════════════════════════════
# 2. EMAIL
# ══════════════════════════════════════════════════════════
@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if len(body.password) < 6:
        raise HTTPException(400, detail="Пароль минимум 6 символов")

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(400, detail="Email уже зарегистрирован")

    user = User(
        name=body.name,
        email=body.email,
        password=hash_password(body.password),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return format_user(user, create_access_token(str(user.id)))


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not user.password or not verify_password(body.password, user.password):
        raise HTTPException(401, detail="Неверный email или пароль")

    return format_user(user, create_access_token(str(user.id)))


# ══════════════════════════════════════════════════════════
# 3. GOOGLE
# ══════════════════════════════════════════════════════════
@router.post("/google")
async def login_google(body: GoogleRequest, db: AsyncSession = Depends(get_db)):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={body.token}"
            )
        if r.status_code != 200:
            raise HTTPException(401, detail="Невалидный токен Google")

        g = r.json()
        google_id = g.get("sub")
        email     = g.get("email")
        name      = g.get("name") or g.get("given_name") or (email.split("@")[0] if email else "Пользователь")
        avatar    = g.get("picture")

        if not google_id:
            raise HTTPException(401, detail="Не удалось получить данные Google")

        # Ищем по google_id
        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if not user and email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                user.google_id = google_id
                if avatar: user.avatar = avatar
                await db.commit()
                await db.refresh(user)

        if not user:
            user = User(google_id=google_id, email=email, name=name, avatar=avatar, is_verified=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return format_user(user, create_access_token(str(user.id)))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Ошибка Google: {str(e)}")


# ══════════════════════════════════════════════════════════
# 4. APPLE
# ══════════════════════════════════════════════════════════
@router.post("/apple")
async def login_apple(body: AppleRequest, db: AsyncSession = Depends(get_db)):
    try:
        decoded  = jwt.decode(body.identityToken, options={"verify_signature": False})
        apple_id = decoded.get("sub")
        email    = decoded.get("email")

        if not apple_id:
            raise HTTPException(401, detail="Невалидный Apple токен")

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
            # Имя из iOS (Apple даёт только при первом входе)
            name = None
            if body.fullName:
                given  = body.fullName.get("givenName", "")
                family = body.fullName.get("familyName", "")
                name   = f"{given} {family}".strip() or None
            name = name or (email.split("@")[0] if email else "Пользователь Apple")

            user = User(apple_id=apple_id, email=email, name=name, is_verified=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return format_user(user, create_access_token(str(user.id)))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"Ошибка Apple: {str(e)}")
