from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str = os.environ.get("DATABASE_URL")

    # === JWT AUTH ===
    SECRET_KEY: str = os.environ.get("SECRET_KEY")
    ALGORITHM: str = os.environ.get("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

    # === EMAIL ===
    EMAIL_HOST: str = os.environ.get("EMAIL_HOST")
    EMAIL_PORT: int = int(os.environ.get("EMAIL_PORT", 587))
    EMAIL_HOST_USER: str = os.environ.get("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD: str = os.environ.get("EMAIL_HOST_PASSWORD")
    EMAIL_FROM: str = os.environ.get("EMAIL_FROM")

    # === PAYMENT GATEWAY ===
    PAYSTACK_SECRET_KEY: str = os.environ.get("PAYSTACK_SECRET_KEY")
    FLUTTERWAVE_SECRET_KEY: str = os.environ.get("FLUTTERWAVE_SECRET_KEY")

    # === DEBUG MODE ===
    DEBUG: bool = os.environ.get("DEBUG", "True").lower() == "true"

settings = Settings()
