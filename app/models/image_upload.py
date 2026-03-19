# app/models/image_upload.py - NEW
from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid
from datetime import datetime

class ImageUploadRecord(Base):
    __tablename__ = "image_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    officer_id = Column(String(100), nullable=True)
    pdf_path = Column(String(500), nullable=False)
    pdf_size_kb = Column(Float, nullable=False)
    num_images = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="completed")
    email_sent = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    uploaded_by = Column(String(255), nullable=True)  # Admin who uploaded
    
    def __repr__(self):
        return f"<ImageUploadRecord {self.email} - {self.num_images} images>"