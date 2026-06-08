from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Emplea Humboldt - Notificaciones"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    PORT: int = 8004

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "noti_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    JWT_SECRET_KEY: str = "cambia-esta-clave-en-produccion"
    JWT_ALGORITHM: str = "HS256"

    # Clave interna que deben enviar los otros microservicios al publicar eventos
    INTERNAL_API_KEY: str = "clave-interna-entre-servicios"

    # Email (AWS SES / SMTP)
    EMAIL_HABILITADO: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@empleahumboldt.edu.co"

    # Push (FCM — Firebase Cloud Messaging)
    PUSH_HABILITADO: bool = False
    FCM_SERVER_KEY: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
