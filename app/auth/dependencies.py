# app/auth/dependencies.py
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

# ADD LOGGING
import logging
logger = logging.getLogger(__name__)

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
    
    # ADD LOGGING
    logger.info(f"🔑 [get_current_existing_officer] Validating token. Token: {token[:50]}...")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        officer_id = payload.get("sub")
        role = payload.get("role")
        
        # ADD LOGGING
        logger.info(f"🔑 [get_current_existing_officer] Decoded payload: officer_id={officer_id}, role={role}")
        
        if role != "existing_officer" or not officer_id:
            logger.error(f"❌ [get_current_existing_officer] Invalid token: role={role}, officer_id={officer_id}")
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
            logger.error(f"❌ [get_current_existing_officer] Officer not found: {officer_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Existing officer not found or inactive"
            )
            
        logger.info(f"✅ [get_current_existing_officer] Officer validated: {officer_id} ({officer.full_name})")
        return officer
    except JWTError as e:
        logger.error(f"❌ [get_current_existing_officer] JWT decode error: {str(e)}")
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
    
    # ADD LOGGING
    logger.info(f"🔑 [get_current_existing_officer_dict] Dashboard token validation")
    logger.info(f"   Token received: {token[:50]}...")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        officer_id = payload.get("sub")
        role = payload.get("role")
        
        # ADD LOGGING
        logger.info(f"🔑 [get_current_existing_officer_dict] Decoded payload:")
        logger.info(f"   officer_id: {officer_id}")
        logger.info(f"   role: {role}")
        logger.info(f"   Full payload: {payload}")
        
        if role != "existing_officer" or not officer_id:
            logger.error(f"❌ [get_current_existing_officer_dict] Invalid token: role={role}, officer_id={officer_id}")
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
            logger.error(f"❌ [get_current_existing_officer_dict] Officer not found in DB: {officer_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Existing officer not found or inactive"
            )
            
        logger.info(f"✅ [get_current_existing_officer_dict] Officer validated successfully")
        logger.info(f"   Officer: {officer.full_name} ({officer.officer_id})")
        logger.info(f"   Status: {officer.status}, Active: {officer.is_active}")
            
        return {
            "officer_id": officer.officer_id,
            "email": officer.email,
            "full_name": officer.full_name,
            "role": "existing_officer",
            "db_id": str(officer.id),
            "category": officer.category,
            "rank": officer.rank
        }
    except JWTError as e:
        logger.error(f"❌ [get_current_existing_officer_dict] JWT decode error: {str(e)}")
        logger.error(f"   SECRET_KEY used: {SECRET_KEY[:20]}...")
        logger.error(f"   ALGORITHM used: {ALGORITHM}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"❌ [get_current_existing_officer_dict] Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )