from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # === DATABASE ===
    DATABASE_URL: str

    # === JWT AUTH ===
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # === EMAIL ===
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_FROM: str

    # === PAYMENT GATEWAY ===
    PAYSTACK_SECRET_KEY: str
    FLUTTERWAVE_SECRET_KEY: str

    # === DEBUG MODE ===
    DEBUG: bool = True   # 👈 added

    class Config:
        env_file = ".env"

settings = Settings()
