# app/utils/jwt_handler.py (compatibility version)
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import python-jose first, then PyJWT as fallback
try:
    from jose import JWTError, jwt
    JWT_LIB = "python-jose"
    logger.info("Using python-jose for JWT operations")
except ImportError:
    try:
        import jwt
        from jwt import PyJWTError as JWTError
        JWT_LIB = "PyJWT"
        logger.info("Using PyJWT for JWT operations")
    except ImportError:
        raise ImportError(
            "No JWT library found. Please install either 'python-jose' or 'PyJWT'\n"
            "Run: pip install python-jose[cryptography]\n"
            "Or: pip install PyJWT"
        )

from app.config import settings

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT refresh token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """
    Verify JWT token
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT verification failed: {str(e)}")
        return {"error": "Invalid token"}


def decode_token(token: str):
    """
    Decode JWT token without verification (use with caution)
    """
    try:
        if JWT_LIB == "python-jose":
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_signature": False})
        else:  # PyJWT
            return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM], options={"verify_signature": False})
    except Exception as e:
        logger.error(f"JWT decode failed: {str(e)}")
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired
    """
    payload = decode_token(token)
    if not payload or "exp" not in payload:
        return True
    
    exp_timestamp = payload["exp"]
    current_timestamp = datetime.utcnow().timestamp()
    
    return exp_timestamp < current_timestamp