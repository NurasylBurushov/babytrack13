from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User
from schemas import SendOTPRequest, VerifyOTPRequest, TokenResponse
from auth import create_access_token
from sms import create_otp, verify_otp, send_sms

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/send-otp", summary="Отправить SMS с кодом")
async def send_otp(body: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    Шаг 1: отправляем OTP код на телефон.
    В DEBUG режиме код всегда 123456.
    """
    code = await create_otp(body.phone, db)
    sent = await send_sms(body.phone, code)

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось отправить SMS. Попробуйте позже.",
        )

    return {"message": "SMS отправлен", "phone": body.phone}


@router.post("/verify-otp", response_model=TokenResponse, summary="Подтвердить код из SMS")
async def verify(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    Шаг 2: проверяем код, выдаём JWT токен.
    Если пользователь новый — создаём аккаунт.
    """
    ok = await verify_otp(body.phone, body.code, db)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истёкший код",
        )

    # Ищем или создаём пользователя
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()
    is_new = user is None

    if is_new:
        user = User(
            phone=body.phone,
            name=body.name or body.phone,
            is_verified=True,
        )
        db.add(user)
        await db.flush()

    token = create_access_token(str(user.id))

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_new_user=is_new,
    )
