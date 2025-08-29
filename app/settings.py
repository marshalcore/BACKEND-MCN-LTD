from pydantic import BaseSettings

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str

    # === JWT ===
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # === SMTP ===
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_FROM: str

    # === PAYMENT KEYS ===
    PAYSTACK_SECRET_KEY: str
    FLUTTERWAVE_SECRET_KEY: str = ""  # Placeholder for now

    # === DEBUG MODE ===
    DEBUG: bool = True   # 👈 added (default True, override in .env if needed)

    class Config:
        env_file = ".env"

settings = Settings()
