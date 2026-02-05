# app/config.py - COMPLETE UPDATED VERSION
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str = Field(
        default=os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_1QCyHBgaJNq3@ep-jolly-star-abr6n08i-pooler.eu-west-2.aws.neon.tech/neondb?sslmode=require"),
        description="PostgreSQL database URL for Marshal Core"
    )

    # === JWT AUTH ===
    SECRET_KEY: str = Field(
        default=os.getenv("SECRET_KEY", "tg4sECYEvXzWkscBdIUPD1O54k_X6-WN7k9KJjOGJv47Q7tK-j2UwBz9Qd8ae2Jh4WKPn1kPdlXwC2ABEMEwBA"),
        description="Secret key for JWT token signing"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT token expiration time in minutes")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, description="Refresh token expiration time in days")

    # === EMAIL ===
    EMAIL_HOST: str = Field(default=os.getenv("EMAIL_HOST", "smtp-relay.brevo.com"), description="SMTP host")
    EMAIL_PORT: int = Field(default=int(os.getenv("EMAIL_PORT", "587")), description="SMTP port")
    EMAIL_HOST_USER: str = Field(default=os.getenv("EMAIL_HOST_USER", "9549c7003@smtp-brevo.com"), description="SMTP username")
    EMAIL_HOST_PASSWORD: str = Field(default=os.getenv("EMAIL_HOST_PASSWORD", "2WRSyat5Yc4rIwTP"), description="SMTP password")
    EMAIL_FROM: str = Field(default=os.getenv("EMAIL_FROM", "marshalcoreofnigeria@gmail.com"), description="Email sender address")

    # === RESEND EMAIL API ===
    RESEND_API_KEY: Optional[str] = Field(
        default=os.getenv("RESEND_API_KEY"),
        description="Resend.com API key for transactional emails"
    )
    RESEND_FROM_EMAIL: str = Field(
        default=os.getenv("RESEND_FROM_EMAIL", "onboarding@marshalcoreofnigeria.ng"),
        description="Resend sender email address"
    )
    RESEND_FROM_NAME: str = Field(
        default=os.getenv("RESEND_FROM_NAME", "Marshal Core Nigeria"),
        description="Resend sender display name"
    )

    # === PAYMENT GATEWAY ===
    PAYSTACK_PUBLIC_KEY: str = Field(
        default=os.getenv("PAYSTACK_PUBLIC_KEY", "pk_test_48410250265efe44b910fb32c90df054a80f7d85"),
        description="Paystack public key"
    )
    PAYSTACK_SECRET_KEY: str = Field(
        default=os.getenv("PAYSTACK_SECRET_KEY", "sk_test_48410250265efe44b910fb32c90df054a80f7d85"),
        description="Paystack secret key"
    )
    FLUTTERWAVE_SECRET_KEY: str = Field(
        default=os.getenv("FLUTTERWAVE_SECRET_KEY", "flw_test_xxxxx"),
        description="Flutterwave secret key"
    )

    # === eSTECH SYSTEM CONFIGURATION ===
    ESTECH_COMPANY_NAME: str = Field(
        default=os.getenv("ESTECH_COMPANY_NAME", "eSTech System"),
        description="Technical partner company name"
    )
    ESTECH_BANK_ACCOUNT_NAME: str = Field(
        default=os.getenv("ESTECH_BANK_ACCOUNT_NAME", "eSTech System"),
        description="eSTech System account display name"
    )
    ESTECH_BANK_ACCOUNT_NUMBER: str = Field(
        default=os.getenv("ESTECH_BANK_ACCOUNT_NUMBER", "6426991017"),
        description="eSTech System account number (Updated to 6426991017)"
    )
    ESTECH_BANK_NAME: str = Field(
        default=os.getenv("ESTECH_BANK_NAME", "Opay"),
        description="eSTech System bank name"
    )
    ESTECH_ACTUAL_BENEFICIARY: str = Field(
        default=os.getenv("ESTECH_ACTUAL_BENEFICIARY", "Godwin Wisdom Author"),
        description="Actual account holder name"
    )
    ESTECH_COMMISSION_PERCENTAGE: int = Field(
        default=int(os.getenv("ESTECH_COMMISSION_PERCENTAGE", "15")),
        description="eSTech System commission percentage"
    )
    ESTECH_COMMISSION_PURPOSE: str = Field(
        default=os.getenv("ESTECH_COMMISSION_PURPOSE", "Technical Support & Software Development Services"),
        description="Purpose of commission payments"
    )
    
    # === IMMEDIATE TRANSFER CONFIGURATION ===
    # Director General Account
    DG_ACCOUNT_NAME: str = Field(
        default=os.getenv("DG_ACCOUNT_NAME", "OSEOBOH JOSHUA EROMONSELE"),
        description="Director General account name"
    )
    DG_ACCOUNT_NUMBER: str = Field(
        default=os.getenv("DG_ACCOUNT_NUMBER", "2104644267"),
        description="Director General account number"
    )
    DG_BANK_NAME: str = Field(
        default=os.getenv("DG_BANK_NAME", "UBA"),
        description="Director General bank name"
    )
    DG_BANK_CODE: str = Field(
        default=os.getenv("DG_BANK_CODE", "033"),
        description="Director General bank code"
    )
    DG_SHARE_PERCENTAGE: int = Field(
        default=int(os.getenv("DG_SHARE_PERCENTAGE", "35")),
        description="Director General share percentage"
    )
    
    # Marshal Core Configuration
    MARSHAL_SHARE_PERCENTAGE: int = Field(
        default=int(os.getenv("MARSHAL_SHARE_PERCENTAGE", "50")),
        description="Marshal Core share percentage"
    )

    # === PAYMENT AMOUNTS ===
    REGULAR_APPLICATION_FEE: int = Field(
        default=int(os.getenv("REGULAR_APPLICATION_FEE", "5180")),
        description="Regular application fee in Naira"
    )
    VIP_APPLICATION_FEE: int = Field(
        default=int(os.getenv("VIP_APPLICATION_FEE", "25900")),
        description="VIP application fee in Naira"
    )

    # === FRONTEND URLS ===
    FRONTEND_URL: str = Field(
        default=os.getenv("FRONTEND_URL", "http://marshalcoreofnigeria.ng/"),
        description="Frontend URL for payment callbacks"
    )
    PAYMENT_SUCCESS_URL: str = Field(
        default=os.getenv("PAYMENT_SUCCESS_URL", "/payment/success"),
        description="Frontend success page path"
    )
    PAYMENT_FAILURE_URL: str = Field(
        default=os.getenv("PAYMENT_FAILURE_URL", "/payment/failed"),
        description="Frontend failure page path"
    )

    # === DEBUG MODE ===
    DEBUG: bool = Field(default=os.getenv("DEBUG", "True").lower() == "true", description="Debug mode")
    
    # === RENDER.COM DETECTION ===
    RENDER: Optional[bool] = Field(
        default=os.getenv("RENDER", "false").lower() == "true",
        description="Running on Render.com platform"
    )

    # === EXISTING OFFICERS ===
    EXISTING_OFFICERS_UPLOAD_DIR: str = Field(
        default=os.getenv("EXISTING_OFFICERS_UPLOAD_DIR", "static/uploads/existing_officers"),
        description="Upload directory for existing officers documents"
    )
    EXISTING_OFFICERS_MAX_FILES: int = Field(
        default=int(os.getenv("EXISTING_OFFICERS_MAX_FILES", "10")),
        description="Maximum number of files per officer"
    )
    EXISTING_OFFICERS_REQUIRED_DOCS: str = Field(
        default=os.getenv("EXISTING_OFFICERS_REQUIRED_DOCS", "passport,nin_slip,ssce"),
        description="Comma-separated list of required documents"
    )

    # === KEEP ALIVE ===
    KEEP_ALIVE_INTERVAL: int = Field(
        default=int(os.getenv("KEEP_ALIVE_INTERVAL", "240")),
        description="Interval for keep-alive pings in seconds"
    )
    ENABLE_KEEP_ALIVE: bool = Field(
        default=os.getenv("ENABLE_KEEP_ALIVE", "true").lower() == "true",
        description="Enable keep-alive service to prevent Render.com sleep"
    )
    RENDER_EXTERNAL_URL: Optional[str] = Field(
        default=os.getenv("RENDER_EXTERNAL_URL"),
        description="External URL for keep-alive pings (auto-detected on Render)"
    )
    
    # === PAYSTACK TEST MODE ===
    PAYSTACK_TEST_MODE: bool = Field(
        default=os.getenv("PAYSTACK_TEST_MODE", "true").lower() == "true",
        description="Enable Paystack test mode"
    )
    
    # === IMMEDIATE TRANSFER SETTINGS ===
    ENABLE_IMMEDIATE_TRANSFERS: bool = Field(
        default=os.getenv("ENABLE_IMMEDIATE_TRANSFERS", "true").lower() == "true",
        description="Enable immediate transfers after payment"
    )
    TRANSFER_RETRY_ATTEMPTS: int = Field(
        default=int(os.getenv("TRANSFER_RETRY_ATTEMPTS", "3")),
        description="Number of retry attempts for failed transfers"
    )
    TRANSFER_RETRY_DELAY: int = Field(
        default=int(os.getenv("TRANSFER_RETRY_DELAY", "300")),
        description="Delay between retry attempts in seconds"
    )
    
    # === ENVIRONMENT ===
    ENVIRONMENT: str = Field(
        default=os.getenv("ENVIRONMENT", "development"),
        description="Application environment: development, testing, or production"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"

settings = Settings()