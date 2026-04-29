import httpx
import os
import re

async def send_sms(phone: str, code: str) -> bool:
    login = os.getenv("SMSC_LOGIN")
    password = os.getenv("SMSC_PASSWORD")
    
    if not login or not password:
        print("ОШИБКА: Не заданы SMSC_LOGIN и SMSC_PASSWORD")
        return False

    # Чистим номер — оставляем только цифры
    clean = re.sub(r'\D', '', phone)
    
    # SMSC.kz для Казахстана принимает формат 77XXXXXXXXX (11 цифр)
    if clean.startswith('8') and len(clean) == 11:
        clean = '7' + clean[1:]
    elif len(clean) == 10:
        clean = '7' + clean
    
    print(f"📱 Отправка SMS на: {clean}")  # увидишь в логах Railway
    
    message = f"Код Sabi Track: {code}"
    url = "https://smsc.kz/sys/send.php"
    
    payload = {
        "login": login,
        "psw": password,
        "phones": clean,
        "mes": message,
        "charset": "utf-8"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=payload)
            print(f"📨 SMSC ответ: {response.text}")  # увидишь точный ответ
            
            if "OK" in response.text:
                print(f"✅ SMS отправлено на {clean}")
                return True
            else:
                print(f"❌ Ошибка SMSC: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Сетевая ошибка: {e}")
        return False 
