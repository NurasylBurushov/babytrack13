import os
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    SMSC_LOGIN: str
    SMSC_PASSWORD: str

    # Cloudflare R2 (S3-совместимое хранилище). Опционально — пока не заданы в Railway, приложение всё равно стартует.
    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY: str | None = None
    R2_SECRET_KEY: str | None = None
    R2_BUCKET: str | None = None
    R2_ENDPOINT: str | None = None
    # Публичная база для ссылок на объекты (R2 Custom Domain или r2.dev), без завершающего /
    R2_PUBLIC_BASE_URL: str | None = None

    @property
    def r2_configured(self) -> bool:
        return all(
            (
                self.R2_ACCOUNT_ID,
                self.R2_ACCESS_KEY,
                self.R2_SECRET_KEY,
                self.R2_BUCKET,
                self.R2_ENDPOINT,
                self.R2_PUBLIC_BASE_URL,
            )
        )

    class Config:
        env_file = os.path.join(BASE_DIR, ".env")
        extra = "ignore"


def get_settings():
    return Settings()