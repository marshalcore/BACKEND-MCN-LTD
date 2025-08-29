from sqlalchemy import Column, String, DateTime
from datetime import datetime, timedelta
import uuid

from app.database import Base

class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False)
    code = Column(String, nullable=False)
    purpose = Column(String, nullable=False)  # e.g., "admin_reset"
    expires_at = Column(DateTime, nullable=False, default=lambda: datetime.utcnow() + timedelta(minutes=10))

    def __repr__(self):
        return f"<VerificationCode email={self.email} purpose={self.purpose}>"
