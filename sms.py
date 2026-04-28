import httpx
import os

async def send_sms(phone: str, code: str) -> bool:
    # БЕРЕМ ЛОГИН И ПАРОЛЬ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (ОБ ЭТОМ НИЖЕ)
    login = os.getenv("SMSC_LOGIN")
    password = os.getenv("SMSC_PASSWORD")
    
    if not login or not password:
        print("ОШИБКА: Не заданы переменные SMSC_LOGIN и SMSC_PASSWORD в .env")
        return False

    message = f"Код Sabi Track: {code}"
    url = "https://smsc.kz/sys/send.php"
    
    # Формируем тело запроса (smsc.kz требует формат x-www-form-urlencoded)
    payload = {
        "login": login,
        "psw": password,
        "phones": phone,
        "mes": message
    }

    try:
        async with httpx.AsyncClient() as client:
            # data= отправляет как form-data, json= отправил бы как JSON (smsc.kz не поймет)
            response = await client.post(url, data=payload)
            
            # smsc.kz возвращает строку "OK..." в случае успеха
            if "OK" in response.text:
                print(f"SMS успешно отправлено на {phone}")
                return True
            else:
                print(f"Ошибка SMS сервиса: {response.text}")
                return False
    except Exception as e:
        print(f"Сетевая ошибка при отправке SMS: {e}")
        return False
