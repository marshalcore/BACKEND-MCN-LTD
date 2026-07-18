# app/routes/auth.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.utils.jwt_handler import decode_token, create_access_token
from app.database import get_db
from app.models.pre_applicant import PreApplicant

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class VerifyTokenRequest(BaseModel):
    token: str

class VerifyTokenResponse(BaseModel):
    status: str
    message: str
    password: str = None
    email: str = None

@router.post("/verify-token", response_model=VerifyTokenResponse)
async def verify_token(request: VerifyTokenRequest):
    """
    Verify a JWT token and extract password if present.
    Used by frontend apply.html page to verify account recovery tokens.
    """
    try:
        payload = decode_token(request.token)
        
        if not payload:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        
        # Extract password from token if present
        password = payload.get("password", None)
        email = payload.get("email", None)
        
        return VerifyTokenResponse(
            status="success",
            message="Token verified successfully",
            password=password,
            email=email
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token verification failed: {str(e)}")

class VerifyRecoveryRequest(BaseModel):
    token: str

class VerifyRecoveryResponse(BaseModel):
    status: str
    message: str
    email: str = None

@router.post("/verify-recovery", response_model=VerifyRecoveryResponse)
async def verify_recovery(request: VerifyRecoveryRequest):
    """
    Verify a recovery token and extract email.
    Used by frontend apply.html to get email for password entry form.
    """
    try:
        payload = decode_token(request.token)
        
        if not payload:
            raise HTTPException(status_code=400, detail="Invalid or expired recovery token")
        
        # Extract email from token
        email = payload.get("email", None)
        
        if not email:
            raise HTTPException(status_code=400, detail="Token does not contain email")
        
        return VerifyRecoveryResponse(
            status="success",
            message="Recovery token verified",
            email=email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Recovery verification failed: {str(e)}")

class GetAccessTokenRequest(BaseModel):
    email: str
    password: str

class GetAccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/get-access-token", response_model=GetAccessTokenResponse)
async def get_access_token(request: GetAccessTokenRequest, db: Session = Depends(get_db)):
    """
    Generate an access token after password verification.
    Used by frontend to grant access to protected application pages.
    """
    # Verify the password first
    pre_applicant = db.query(PreApplicant).filter(
        PreApplicant.email == request.email.lower()
    ).first()
    
    if not pre_applicant:
        raise HTTPException(status_code=401, detail="User not found")
    
    if pre_applicant.application_password != request.password:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Create access token for VIP page
    from datetime import timedelta
    access_token = create_access_token(
        data={
            "sub": str(pre_applicant.id),
            "email": pre_applicant.email,
            "type": "vip_access",
            "verified": True
        },
        expires_delta=timedelta(hours=24)  # Valid for 24 hours
    )
    
    return GetAccessTokenResponse(
        access_token=access_token,
        token_type="bearer"
    )
