# app/services/existing_officer_service.py
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from app.models.existing_officer import ExistingOfficer
from app.schemas.existing_officer import (
    ExistingOfficerRegister,
    ExistingOfficerVerify,
    ExistingOfficerUpdate
)
from app.utils.hash import hash_password, verify_password  # FIXED IMPORT
from passlib.context import CryptContext
from app.utils.upload import save_upload

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Mock verification service (to be replaced with actual verification logic)
class OfficerVerificationService:
    """Service to verify existing officer credentials against legacy system"""
    
    @staticmethod
    def verify_officer_credentials(officer_id: str, email: str) -> Dict[str, Any]:
        """
        Mock verification against legacy system.
        In production, this would connect to external API or database.
        """
        # TODO: Replace with actual verification logic
        # For now, we'll accept any officer_id that matches pattern
        
        # Basic validation
        if not re.match(r'^[A-Za-z0-9\-_]{3,50}$', officer_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid officer ID format"
            )
        
        # Email validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Mock verification logic
        # In real system, this would check against external database
        officer_data = {
            "verified": True,
            "officer_id": officer_id,
            "email": email,
            "exists_in_legacy": True,
            "message": "Officer credentials verified successfully"
        }
        
        return officer_data


class ExistingOfficerService:
    """Service for managing existing officers"""
    
    @staticmethod
    def verify_officer(
        db: Session, 
        verify_data: ExistingOfficerVerify
    ) -> Dict[str, Any]:
        """Verify officer credentials"""
        logger.info(f"Verifying officer: {verify_data.officer_id}")
        
        # Check if officer already registered
        existing_record = db.query(ExistingOfficer).filter(
            (ExistingOfficer.officer_id == verify_data.officer_id) |
            (ExistingOfficer.email == verify_data.email)
        ).first()
        
        if existing_record:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Officer already registered in the system"
            )
        
        # Verify against legacy system
        verification_service = OfficerVerificationService()
        verification_result = verification_service.verify_officer_credentials(
            verify_data.officer_id,
            verify_data.email
        )
        
        if not verification_result.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer credentials not found in legacy system"
            )
        
        return {
            "verified": True,
            "message": "Officer credentials verified successfully",
            "officer_data": verification_result
        }
    
    @staticmethod
    def register_officer(
        db: Session,
        register_data: ExistingOfficerRegister,
        created_by: Optional[str] = "system"
    ) -> ExistingOfficer:
        """Register a new existing officer"""
        logger.info(f"Registering existing officer: {register_data.officer_id}")
        
        # Check for duplicates
        existing_officer = db.query(ExistingOfficer).filter(
            (ExistingOfficer.officer_id == register_data.officer_id) |
            (ExistingOfficer.email == register_data.email) |
            (ExistingOfficer.nin_number == register_data.nin_number)
        ).first()
        
        if existing_officer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Officer with these credentials already exists"
            )
        
        # Create new officer record
        officer = ExistingOfficer(
            officer_id=register_data.officer_id,
            email=register_data.email,
            phone=register_data.phone,
            password_hash=hash_password(register_data.password),
            full_name=register_data.full_name,
            nin_number=register_data.nin_number,
            gender=register_data.gender,
            date_of_birth=register_data.date_of_birth,
            place_of_birth=register_data.place_of_birth,
            nationality=register_data.nationality,
            marital_status=register_data.marital_status,
            residential_address=register_data.residential_address,
            state_of_residence=register_data.state_of_residence,
            local_government_residence=register_data.local_government_residence,
            country_of_residence=register_data.country_of_residence,
            state_of_origin=register_data.state_of_origin,
            local_government_origin=register_data.local_government_origin,
            rank=register_data.rank,
            position=register_data.position,
            years_of_service=register_data.years_of_service,
            service_number=register_data.service_number,
            religion=register_data.religion,
            additional_skills=register_data.additional_skills,
            bank_name=register_data.bank_name,
            account_number=register_data.account_number,
            status='pending',
            is_verified=False,
            is_active=True,
            created_by=created_by
        )
        
        try:
            db.add(officer)
            db.commit()
            db.refresh(officer)
            logger.info(f"Existing officer registered successfully: {officer.id}")
            return officer
        except Exception as e:
            db.rollback()
            logger.error(f"Error registering existing officer: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register officer"
            )
    
    @staticmethod
    def upload_document(
        db: Session,
        officer_id: str,
        file: UploadFile,
        document_type: str,
        description: Optional[str] = None
    ) -> str:
        """Upload document for existing officer"""
        logger.info(f"Uploading document {document_type} for officer {officer_id}")
        
        # Get officer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )
        
        # Save upload
        try:
            file_path = save_upload(file, f"existing_officers/{document_type}")
            
            # Update officer record with document path
            document_field_map = {
                'passport': 'passport_photo',
                'nin_slip': 'nin_slip',
                'ssce': 'ssce_certificate',
                'birth_certificate': 'birth_certificate',
                'appointment_letter': 'letter_of_first_appointment',
                'promotion_letter': 'promotion_letters',
                'service_certificate': 'service_certificate',
                'medical_certificate': 'medical_certificate',
                'guarantor_form': 'guarantor_form',
                'other': 'other_documents'
            }
            
            if document_type in document_field_map:
                field_name = document_field_map[document_type]
                setattr(officer, field_name, file_path)
            else:
                # Handle other documents as JSON array
                current_docs = officer.other_documents or '[]'
                # TODO: Parse and update JSON array
                pass
            
            officer.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Document uploaded successfully: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload document: {str(e)}"
            )
    
    @staticmethod
    def get_officer_by_id(db: Session, officer_id: str) -> Optional[ExistingOfficer]:
        """Get officer by ID"""
        return db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
    
    @staticmethod
    def get_officer_by_email(db: Session, email: str) -> Optional[ExistingOfficer]:
        """Get officer by email"""
        return db.query(ExistingOfficer).filter(
            ExistingOfficer.email == email
        ).first()
    
    @staticmethod
    def update_officer_status(
        db: Session,
        officer_id: str,
        update_data: ExistingOfficerUpdate,
        updated_by: str
    ) -> ExistingOfficer:
        """Update officer status (admin only)"""
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Update fields
        if update_data.status is not None:
            officer.status = update_data.status
            if update_data.status == 'verified':
                officer.is_verified = True
                officer.verification_date = datetime.utcnow()
                officer.verified_by = updated_by
        
        if update_data.is_active is not None:
            officer.is_active = update_data.is_active
        
        if update_data.admin_notes is not None:
            officer.admin_notes = update_data.admin_notes
        
        if update_data.rejection_reason is not None:
            officer.rejection_reason = update_data.rejection_reason
        
        officer.updated_by = updated_by
        officer.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(officer)
            return officer
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating officer status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update officer status"
            )
    
    @staticmethod
    def authenticate_officer(
        db: Session,
        officer_id: str,
        password: str
    ) -> Optional[ExistingOfficer]:
        """Authenticate existing officer"""
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id,
            ExistingOfficer.is_active == True
        ).first()
        
        if not officer:
            return None
        
        if not verify_password(password, officer.password_hash):
            return None
        
        # Update last login
        officer.last_login = datetime.utcnow()
        db.commit()
        
        return officer
    
    @staticmethod
    def get_all_officers(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[ExistingOfficer]:
        """Get all existing officers with optional filtering"""
        query = db.query(ExistingOfficer)
        
        if status:
            query = query.filter(ExistingOfficer.status == status)
        
        return query.offset(skip).limit(limit).all()