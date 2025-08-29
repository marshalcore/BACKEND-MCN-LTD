# app/utils/token.py
from datetime import datetime, timedelta
import random
import string
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.models.officer import Officer
from app.database import get_db
from app.config import settings
from pydantic import BaseModel
from app.utils.otp import normalize_purpose, store_verification_code, verify_otp


# Secret and Algorithm
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = int(settings.ACCESS_TOKEN_EXPIRE_MINUTES)
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days for refresh tokens

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="officer/login")


class TokenData(BaseModel):
    unique_id: str | None = None
    type: str | None = None  # 'access' or 'refresh'


async def get_current_officer(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Officer:
    """
    Dependency to get current authenticated officer from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        unique_id: str = payload.get("sub")
        if unique_id is None:
            raise credentials_exception
        token_data = TokenData(unique_id=unique_id)
    except JWTError:
        raise credentials_exception
    
    officer = db.query(Officer).filter(Officer.unique_id == token_data.unique_id).first()
    if officer is None:
        raise credentials_exception
    return officer


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """
    Create JWT token with expiration
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    """
    Decode JWT token without validation (for internal use)
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def create_refresh_token(data: dict) -> str:
    """
    Create refresh token with longer expiration
    """
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_access_token(data, expires_delta)


def verify_refresh_token(token: str) -> dict | None:
    """
    Verify if token is a valid refresh token
    """
    payload = decode_access_token(token)
    if payload and payload.get("type") == "refresh":
        return payload
    return None


# -------------------- OTP UTILS --------------------
def generate_otp(length: int = 6) -> str:
    """Generate a numeric OTP of given length (default 6 digits)."""
    return ''.join(random.choices(string.digits, k=length))
