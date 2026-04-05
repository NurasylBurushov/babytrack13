import httpx
import random
import string
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import OTPCode
from config import settings


def generate_otp() -> str:
    # В DEBUG режиме — всегда 123456
    if settings.DEBUG:
        return "123456"
    return "".join(random.choices(string.digits, k=6))


async def send_sms(phone: str, code: str) -> bool:
    """Отправляет SMS через SMSC.kz или SMS.ru"""
    message = f"BabyTrack: ваш код {code}. Действителен 10 минут."

    if settings.DEBUG:
        print(f"[DEBUG SMS] Phone: {phone}, Code: {code}")
        return True

    if settings.SMS_PROVIDER == "smsc":
        return await _send_smsc(phone, message)
    else:
        return await _send_smsru(phone, message)


async def _send_smsc(phone: str, message: str) -> bool:
    """SMSC.kz — популярный в Казахстане"""
    url = "https://smsc.kz/sys/send.php"
    params = {
        "login": settings.SMSC_LOGIN,
        "psw": settings.SMSC_PASSWORD,
        "phones": phone,
        "mes": message,
        "fmt": 3,       # JSON ответ
        "charset": "utf-8",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            return "error" not in data
    except Exception as e:
        print(f"SMSC error: {e}")
        return False


async def _send_smsru(phone: str, message: str) -> bool:
    """SMS.ru"""
    url = "https://sms.ru/sms/send"
    data = {
        "api_id": settings.SMSRU_API_ID,
        "to": phone,
        "msg": message,
        "json": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, data=data)
            result = resp.json()
            return result.get("status") == "OK"
    except Exception as e:
        print(f"SMS.ru error: {e}")
        return False


async def create_otp(phone: str, db: AsyncSession) -> str:
    """Создаёт OTP код в базе данных"""
    # Инвалидируем старые коды
    await db.execute(
        update(OTPCode)
        .where(OTPCode.phone == phone, OTPCode.is_used == False)
        .values(is_used=True)
    )

    code = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=10)

    otp = OTPCode(phone=phone, code=code, expires_at=expires)
    db.add(otp)
    await db.flush()

    return code


async def verify_otp(phone: str, code: str, db: AsyncSession) -> bool:
    """Проверяет OTP код"""
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.phone == phone,
            OTPCode.code == code,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.utcnow(),
        )
    )
    otp = result.scalar_one_or_none()

    if not otp:
        return False

    otp.is_used = True
    return True
