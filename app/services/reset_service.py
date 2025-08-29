# app/services/reset_service.py

from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.models.officer import Officer
from app.models.admin import Admin
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
RESET_TOKEN_EXPIRE_MINUTES = 30


def create_reset_token(email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def update_password(db: Session, email: str, new_password: str, is_admin: bool = False):
    Model = Admin if is_admin else Officer
    user = db.query(Model).filter(Model.email == email).first()

    if user:
        user.password_hash = pwd_context.hash(new_password)
        db.commit()
