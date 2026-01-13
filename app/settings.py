# app/settings.py
import os

class Settings:
    # === DATABASE ===
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    
    # === JWT ===
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # === SMTP ===
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER: str = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD: str = os.getenv("EMAIL_HOST_PASSWORD")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM")
    
    # === PAYMENT KEYS ===
    PAYSTACK_SECRET_KEY: str = os.getenv("PAYSTACK_SECRET_KEY")
    FLUTTERWAVE_SECRET_KEY: str = os.getenv("FLUTTERWAVE_SECRET_KEY", "")
    
    # === DEBUG MODE ===
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    def validate(self):
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is required")
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable is required")

settings = Settings()
settings.validate()