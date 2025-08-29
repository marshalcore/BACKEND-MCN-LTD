from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.database import get_db
from sqlalchemy.orm import Session
from app.models.admin import Admin
from app.models.officer import Officer
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "secret")
ALGORITHM = "HS256"

bearer_scheme = HTTPBearer()

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Admin:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        role = payload.get("role")

        if role != "admin" or not email:
            raise HTTPException(status_code=401, detail="Invalid admin token")
        
        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        return admin

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_officer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Officer:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid officer token")

        officer = db.query(Officer).filter(Officer.email == email).first()
        if not officer:
            raise HTTPException(status_code=401, detail="Officer not found")

        return officer
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
