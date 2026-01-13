# app/schemas/user.py
"""
Basic User schema for authentication in PDF endpoints
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from uuid import UUID


class User(BaseModel):
    """Basic user schema for PDF authentication"""
    id: str
    role: str
    authenticated: bool
    is_admin: Optional[bool] = False
    email: Optional[str] = None
    name: Optional[str] = None
    
    class Config:
        from_attributes = True


class TokenData(BaseModel):
    """Token data schema"""
    sub: str
    role: str
    exp: Optional[int] = None


class AuthResponse(BaseModel):
    """Authentication response"""
    status: str
    message: str
    user: Optional[User] = None
    access_token: Optional[str] = None


# For backward compatibility with existing code
class CurrentUser(User):
    """Extended user schema for current user context"""
    permissions: Optional[Dict[str, Any]] = None