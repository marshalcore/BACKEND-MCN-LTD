# app/config.py - CLEAN VERSION
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default=os.getenv("DATABASE_URL", ""))
    SECRET_KEY: str = Field(default=os.getenv("SECRET_KEY", ""))
    PAYSTACK_PUBLIC_KEY: str = Field(default=os.getenv("PAYSTACK_PUBLIC_KEY", ""))
    PAYSTACK_SECRET_KEY: str = Field(default=os.getenv("PAYSTACK_SECRET_KEY", ""))
    
    class Config:
        env_file = ".env"

settings = Settings()
