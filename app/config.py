# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str = Field(
        default="postgresql://neondb_owner:npg_1QCyHBgaJNq3@ep-jolly-star-abr6n08i-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
        description="PostgreSQL database URL for Marshal Core"
    )

    # === JWT AUTH ===
    SECRET_KEY: str = Field(
        default="tg4sECYEvXzWkscBdIUPD1O54k_X6-WN7k9KJjOGJv47Q7tK-j2UwBz9Qd8ae2Jh4WKPn1kPdlXwC2ABEMEwBA",
        description="Secret key for JWT token signing"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration time in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration time in days")

    # === EMAIL ===
    EMAIL_HOST: str = Field(default="smtp-relay.brevo.com", description="SMTP host")
    EMAIL_PORT: int = Field(default=587, description="SMTP port")
    EMAIL_HOST_USER: str = Field(default="9549c7003@smtp-brevo.com", description="SMTP username")
    EMAIL_HOST_PASSWORD: str = Field(default="2WRSyat5Yc4rIwTP", description="SMTP password")
    EMAIL_FROM: str = Field(default="marshalcoreofnigeria@gmail.com", description="Email sender address")

    # === PAYMENT GATEWAY ===
    PAYSTACK_SECRET_KEY: str = Field(
        default="sk_test_48410250265efe44b910fb32c90df054a80f7d85",
        description="Paystack secret key"
    )
    FLUTTERWAVE_SECRET_KEY: str = Field(
        default="flw_test_xxxxx",
        description="Flutterwave secret key"
    )

    # === DEBUG MODE ===
    DEBUG: bool = Field(default=True, description="Debug mode")

    # === EXISTING OFFICERS ===
    EXISTING_OFFICERS_UPLOAD_DIR: str = Field(
        default="static/uploads/existing_officers",
        description="Upload directory for existing officers documents"
    )
    EXISTING_OFFICERS_MAX_FILES: int = Field(default=10, description="Maximum number of files per officer")
    EXISTING_OFFICERS_REQUIRED_DOCS: str = Field(
        default="passport,nin_slip,ssce",
        description="Comma-separated list of required documents"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()