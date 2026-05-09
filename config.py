from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # База данных
    DATABASE_URL: str = "postgresql://postgres:oytWpVABQkzfHyKHfvGjffybkUdZnAmT@postgres.railway.internal:5432/railway" 
    
    # Секретный ключ для JWT токенов
    SECRET_KEY: str = "sabitrack_secret_2024_abcdef123456"
    
    # Google OAuth (То, что нам нужно!)
    GOOGLE_CLIENT_ID: str = "981994412149-k7ikgpqkn674ova78e2hr75im80cqguj.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "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"
    
    # СМС сервис (замените названия на те, что у вас в коде, если они другие)
    SMSC_LOGIN: str = "Nurs221"
    SMSC_PASSWORD: str = "Yfhenjkexibq7"

    # Pydantic сам найдет файл .env и прочитает оттуда переменные
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
