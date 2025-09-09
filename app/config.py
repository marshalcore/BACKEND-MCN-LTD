from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str = Field(default=os.environ.get("DATABASE_URL", ""), description="PostgreSQL database URL")

    # === JWT AUTH ===
    SECRET_KEY: str = Field(default=os.environ.get("SECRET_KEY", ""), description="Secret key for JWT token signing")
    ALGORITHM: str = Field(default=os.environ.get("ALGORITHM", "HS256"), description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30)), description="JWT token expiration time in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7)), description="Refresh token expiration time in days")

    # === EMAIL ===
    EMAIL_HOST: str = Field(default=os.environ.get("EMAIL_HOST", ""), description="SMTP host")
    EMAIL_PORT: int = Field(default=int(os.environ.get("EMAIL_PORT", 587)), description="SMTP port")
    EMAIL_HOST_USER: str = Field(default=os.environ.get("EMAIL_HOST_USER", ""), description="SMTP username")
    EMAIL_HOST_PASSWORD: str = Field(default=os.environ.get("EMAIL_HOST_PASSWORD", ""), description="SMTP password")
    EMAIL_FROM: str = Field(default=os.environ.get("EMAIL_FROM", ""), description="Email sender address")

    # === PAYMENT GATEWAY ===
    PAYSTACK_SECRET_KEY: str = Field(default=os.environ.get("PAYSTACK_SECRET_KEY", ""), description="Paystack secret key")
    FLUTTERWAVE_SECRET_KEY: str = Field(default=os.environ.get("FLUTTERWAVE_SECRET_KEY", ""), description="Flutterwave secret key")

    # === DEBUG MODE ===
    DEBUG: bool = Field(default=os.environ.get("DEBUG", "True").lower() == "true", description="Debug mode")

    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
