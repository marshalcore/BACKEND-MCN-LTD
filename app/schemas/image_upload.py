# app/schemas/image_upload.py - NEW
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class ImageUploadRequest(BaseModel):
    email: EmailStr
    officer_id: Optional[str] = None
    notes: Optional[str] = None

class ImageUploadResponse(BaseModel):
    status: str
    message: str
    pdf_path: str
    pdf_size_kb: float
    num_images: int
    email_sent: bool
    timestamp: datetime
    
class ImageUploadHistory(BaseModel):
    id: str
    email: str
    officer_id: Optional[str]
    pdf_path: str
    pdf_size_kb: float
    num_images: int
    created_at: datetime
    status: str
    email_sent: bool
    uploaded_by: Optional[str]
    
    class Config:
        from_attributes = True