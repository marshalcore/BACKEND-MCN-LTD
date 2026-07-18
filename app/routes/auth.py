# app/routes/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.jwt_handler import decode_token

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
