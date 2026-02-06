from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime, timedelta
import uuid

from app.database import Base

class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, index=True)
    code = Column(String(16), nullable=False)
    purpose = Column(String, nullable=False, default="email_verification")  # e.g., "email_verification"
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(minutes=20))

    def __repr__(self):
        return f"<VerificationCode email={self.email} purpose={self.purpose} code={self.code}>"