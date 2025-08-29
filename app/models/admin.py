# app/models/admin.py
from sqlalchemy import Column, String, Boolean
from app.database import Base
import uuid

class Admin(Base):
    __tablename__ = "admins"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=False)  
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    is_superuser = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)