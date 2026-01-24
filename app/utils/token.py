# app/utils/token.py
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import get_db
from app.models.officer import Officer
from app.config import settings

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/officer/login")

# In-memory OTP store (for development - use Redis in production)
otp_store = {}

# ==================== JWT FUNCTIONS ====================

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify JWT token
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ==================== AUTH DEPENDENCIES ====================

async def get_current_officer(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Officer:
    """
    Get current officer from JWT token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        officer_id: str = payload.get("sub")
        role: str = payload.get("role")
        
        if officer_id is None or role != "officer":
            raise credentials_exception
        
        officer = db.query(Officer).filter(Officer.officer_id == officer_id).first()
        if officer is None:
            raise credentials_exception
        
        if not officer.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Officer account is deactivated"
            )
        
        return officer
        
    except JWTError:
        raise credentials_exception

# ==================== OTP FUNCTIONS ====================

def generate_otp(length: int = 6) -> str:
    """
    Generate a numeric OTP
    """
    digits = "0123456789"
    return ''.join(secrets.choice(digits) for _ in range(length))

def store_verification_code(email: str, otp: str, purpose: str = "password_reset") -> None:
    """
    Store OTP for verification
    """
    key = f"{email}:{purpose}"
    otp_store[key] = {
        "otp": otp,
        "created_at": datetime.utcnow(),
        "purpose": purpose
    }
    logger.info(f"OTP stored for {email} ({purpose})")

def verify_otp(email: str, otp: str, purpose: str = "password_reset") -> bool:
    """
    Verify OTP
    """
    key = f"{email}:{purpose}"
    
    if key not in otp_store:
        logger.warning(f"No OTP found for {email} ({purpose})")
        return False
    
    otp_data = otp_store[key]
    
    # Check if OTP is expired (10 minutes)
    if (datetime.utcnow() - otp_data["created_at"]).total_seconds() > 600:
        logger.warning(f"OTP expired for {email}")
        del otp_store[key]
        return False
    
    # Verify OTP
    if otp_data["otp"] == otp:
        logger.info(f"OTP verified for {email} ({purpose})")
        del otp_store[key]  # Remove OTP after successful verification
        return True
    
    logger.warning(f"Invalid OTP for {email}")
    return False

# ==================== PASSWORD FUNCTIONS ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Generate password hash
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

# ==================== UTILITY FUNCTIONS ====================

def cleanup_expired_otps() -> None:
    """
    Clean up expired OTPs from store
    """
    expired_keys = []
    current_time = datetime.utcnow()
    
    for key, otp_data in otp_store.items():
        if (current_time - otp_data["created_at"]).total_seconds() > 600:
            expired_keys.append(key)
    
    for key in expired_keys:
        del otp_store[key]
    
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired OTPs")

def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not any(char.isdigit() for char in password):
        errors.append("Password must contain at least one digit")
    
    if not any(char.isupper() for char in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if not any(char.islower() for char in password):
        errors.append("Password must contain at least one lowercase letter")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "strength": "strong" if len(errors) == 0 else "weak"
    }