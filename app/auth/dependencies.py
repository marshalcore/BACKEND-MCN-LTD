# app/auth/dependencies.py - FIXED VERSION
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.database import get_db
from sqlalchemy.orm import Session
from app.models.admin import Admin
from app.models.officer import Officer

# ✅ FIX: Import settings and use consistent JWT configuration
from app.config import settings

# ✅ FIX: Use settings.SECRET_KEY instead of JWT_SECRET_KEY
# This ensures tokens created by Code 2 can be verified by Code 1
SECRET_KEY = settings.SECRET_KEY  # ✅ Changed from os.getenv("JWT_SECRET_KEY", "secret")
ALGORITHM = settings.ALGORITHM    # ✅ Use from settings for consistency

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


def get_current_existing_officer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    """Get current existing officer from JWT token"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        officer_id = payload.get("sub")
        role = payload.get("role")
        
        if role != "existing_officer" or not officer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid existing officer token"
            )
        
        # Import here to avoid circular imports
        from app.models.existing_officer import ExistingOfficer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id,
            ExistingOfficer.is_active == True
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Existing officer not found or inactive"
            )
            
        return officer
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


# NEW: Dependency that returns a dict (for dashboard routes)
def get_current_existing_officer_dict(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> dict:
    """Get current existing officer as dictionary for dashboard routes"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        officer_id = payload.get("sub")
        role = payload.get("role")
        
        if role != "existing_officer" or not officer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid existing officer token"
            )
        
        # Import here to avoid circular imports
        from app.models.existing_officer import ExistingOfficer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id,
            ExistingOfficer.is_active == True
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Existing officer not found or inactive"
            )
            
        return {
            "officer_id": officer.officer_id,
            "email": officer.email,
            "full_name": officer.full_name,
            "role": "existing_officer",
            "db_id": str(officer.id),
            "category": officer.category,
            "rank": officer.rank
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )