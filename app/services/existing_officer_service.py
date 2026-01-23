# app/services/existing_officer_service.py
import logging
import json
import re
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from app.models.existing_officer import ExistingOfficer
from app.schemas.existing_officer import (
    ExistingOfficerRegister,
    ExistingOfficerVerify,
    ExistingOfficerUpdate
)
from app.utils.hash import hash_password, verify_password
from app.utils.email_validator import EmailValidator
from passlib.context import CryptContext
from app.utils.upload import save_upload

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class OfficerIDValidator:
    """Validate and parse officer IDs - UPDATED FOR NEW FORMAT"""
    
    # Officer categories based on ID prefix - MCN, MBT, MBC only
    OFFICER_CATEGORIES = {
        'MCN': 'Marshal Core of Nigeria',
        'MBT': 'Marshal Board of Trustees', 
        'MBC': 'Marshal Board of Committee'
    }
    
    @staticmethod
    def validate_officer_id_format(officer_id: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate NEW officer ID format and extract components
        NEW Format: PREFIX/ALPHANUMERIC/INTAKE  e.g., MCN/001B/031
        Returns: (is_valid, error_message, parsed_data)
        """
        if not officer_id:
            return False, "Officer ID is required", None
        
        officer_id = officer_id.strip().upper()
        
        # NEW Pattern: MCN|MBT|MBC / 3-4 alphanumeric / 3 digits
        pattern = r'^(MCN|MBT|MBC)/([A-Z0-9]{3,4})/(\d{3})$'
        match = re.match(pattern, officer_id)
        
        if not match:
            return False, "Invalid ID format. Use: PREFIX/ALPHANUMERIC/INTAKE (e.g., MCN/001B/031)", None
        
        prefix, alphanumeric, intake = match.groups()
        
        # Check if prefix is valid
        if prefix not in OfficerIDValidator.OFFICER_CATEGORIES:
            valid_prefixes = ', '.join(OfficerIDValidator.OFFICER_CATEGORIES.keys())
            return False, f"Invalid prefix '{prefix}'. Valid prefixes: {valid_prefixes}", None
        
        # Validate intake (3 digits)
        intake_int = int(intake)
        if not (1 <= intake_int <= 999):
            return False, f"Invalid intake '{intake}'. Must be between 001 and 999", None
        
        parsed_data = {
            'original_id': officer_id,
            'prefix': prefix,
            'alphanumeric': alphanumeric,
            'intake': intake,
            'category': OfficerIDValidator.OFFICER_CATEGORIES[prefix],
            'formatted_id': officer_id
        }
        
        return True, "ID format is valid", parsed_data
    
    @staticmethod
    def get_officer_category(officer_id: str) -> Optional[str]:
        """Get officer category from ID prefix"""
        try:
            is_valid, _, parsed_data = OfficerIDValidator.validate_officer_id_format(officer_id)
            if is_valid and parsed_data:
                return parsed_data['category']
        except:
            pass
        return None
    
    @staticmethod
    def generate_officer_id_examples() -> List[str]:
        """Generate example officer IDs for reference"""
        return [
            "MCN/001/031",
            "MCN/001B/123",
            "MBT/A01/456",
            "MBC/123A/789",
            "MCN/ABCD/001",
            "MBT/1234/999",
            "MBC/X1Y2/050"
        ]


# Mock verification service - UPDATED FOR NEW FORMAT
class OfficerVerificationService:
    """Service to verify existing officer credentials against legacy system"""
    
    @staticmethod
    def verify_officer_credentials(officer_id: str, email: str) -> Dict[str, Any]:
        """
        Verify officer credentials with email validation and ID parsing
        """
        # 1. Validate email
        is_email_valid, email_msg = EmailValidator.validate_officer_email(email)
        if not is_email_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email validation failed: {email_msg}"
            )
        
        # 2. Validate officer ID format (NEW FORMAT)
        is_id_valid, id_msg, parsed_id = OfficerIDValidator.validate_officer_id_format(officer_id)
        if not is_id_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Officer ID validation failed: {id_msg}"
            )
        
        # 3. Clean inputs
        officer_id = officer_id.strip().upper()
        email = email.strip().lower()
        
        logger.info(f"Verifying {parsed_id['category']} officer: {officer_id}, Email: {email}")
        
        # 4. Mock legacy system verification
        officer_data = {
            "verified": True,
            "officer_id": officer_id,
            "email": email,
            "exists_in_legacy": True,
            "category": parsed_id['category'],
            "prefix": parsed_id['prefix'],
            "alphanumeric": parsed_id['alphanumeric'],
            "intake": parsed_id['intake'],
            "full_name": f"Verified {parsed_id['category']} Officer",
            "message": f"{parsed_id['category']} officer credentials verified successfully"
        }
        
        # 5. Log verification details
        logger.info(f"""
        ✅ Officer Verification Successful (NEW FORMAT):
           - ID: {officer_id}
           - Category: {parsed_id['category']}
           - Email: {email}
           - Prefix: {parsed_id['prefix']}
           - Alphanumeric: {parsed_id['alphanumeric']}
           - Intake: {parsed_id['intake']}
        """)
        
        return officer_data


class ExistingOfficerService:
    """Service for managing existing officers - UPDATED FOR 2-UPLOAD SYSTEM"""
    
    @staticmethod
    def verify_officer(
        db: Session, 
        verify_data: ExistingOfficerVerify
    ) -> Dict[str, Any]:
        """Verify officer credentials with enhanced validation - UPDATED FOR NEW FORMAT"""
        logger.info(f"Verifying officer: {verify_data.officer_id}")
        
        # Clean and validate input
        officer_id = verify_data.officer_id.strip().upper()
        email = verify_data.email.strip().lower()
        
        # 1. Validate email before checking database
        is_email_valid, email_msg = EmailValidator.validate_officer_email(email)
        if not is_email_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email validation failed: {email_msg}"
            )
        
        # 2. Validate officer ID format (NEW FORMAT)
        is_id_valid, id_msg, parsed_id = OfficerIDValidator.validate_officer_id_format(officer_id)
        if not is_id_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Officer ID validation failed: {id_msg}"
            )
        
        # 3. Check if officer already registered
        existing_record = db.query(ExistingOfficer).filter(
            (ExistingOfficer.officer_id == officer_id) |
            (ExistingOfficer.email == email)
        ).first()
        
        if existing_record:
            if existing_record.officer_id == officer_id:
                detail = f"Officer ID {officer_id} already registered in the system"
            else:
                detail = f"Email {email} already registered in the system"
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail
            )
        
        # 4. Verify against legacy system
        verification_service = OfficerVerificationService()
        verification_result = verification_service.verify_officer_credentials(
            officer_id,
            email
        )
        
        if not verification_result.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer credentials not found in legacy system"
            )
        
        # 5. Return enhanced verification result
        return {
            "verified": True,
            "message": f"{parsed_id['category']} officer verified successfully",
            "officer_data": verification_result,
            "category": parsed_id['category'],
            "id_details": parsed_id
        }
    
    @staticmethod
    def register_officer(
        db: Session,
        register_data: ExistingOfficerRegister,
        created_by: Optional[str] = "system"
    ) -> ExistingOfficer:
        """Register a new existing officer with enhanced validation - UPDATED WITH NEW FIELDS"""
        logger.info(f"Registering existing officer: {register_data.officer_id}")
        
        # Clean and validate input
        officer_id = register_data.officer_id.strip().upper()
        email = register_data.email.strip().lower()
        phone = register_data.phone.strip()
        
        # 1. Validate officer ID format (NEW FORMAT)
        is_id_valid, id_msg, parsed_id = OfficerIDValidator.validate_officer_id_format(officer_id)
        if not is_id_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Officer ID validation failed: {id_msg}"
            )
        
        # 2. Validate email
        is_email_valid, email_msg = EmailValidator.validate_officer_email(email)
        if not is_email_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email validation failed: {email_msg}"
            )
        
        # 3. Validate date of enlistment (NEW FIELD)
        if not register_data.date_of_enlistment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Date of enlistment is required"
            )
        
        # 4. Check for duplicates
        existing_officer = db.query(ExistingOfficer).filter(
            (ExistingOfficer.officer_id == officer_id) |
            (ExistingOfficer.email == email) |
            (ExistingOfficer.nin_number == register_data.nin_number)
        ).first()
        
        if existing_officer:
            if existing_officer.officer_id == officer_id:
                detail = f"Officer ID {officer_id} already exists"
            elif existing_officer.email == email:
                detail = f"Email {email} already registered"
            else:
                detail = "NIN number already registered"
            
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail
            )
        
        # 5. Validate password length
        if len(register_data.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # 6. Prepare the data for creation - INCLUDING NEW FIELDS
        officer_data = {
            "officer_id": officer_id,
            "email": email,
            "phone": phone,
            "password_hash": hash_password(register_data.password),
            # NEW FIELDS
            "date_of_enlistment": register_data.date_of_enlistment,
            "date_of_promotion": register_data.date_of_promotion,
            # Personal Information
            "full_name": register_data.full_name.strip(),
            "nin_number": register_data.nin_number.strip(),
            "gender": register_data.gender if register_data.gender else "Not Specified",
            "date_of_birth": register_data.date_of_birth,
            "place_of_birth": register_data.place_of_birth if register_data.place_of_birth else None,
            "nationality": register_data.nationality if register_data.nationality else "Nigerian",
            "marital_status": register_data.marital_status if register_data.marital_status else None,
            "residential_address": register_data.residential_address.strip(),
            "state_of_residence": register_data.state_of_residence if register_data.state_of_residence else None,
            "local_government_residence": register_data.local_government_residence if register_data.local_government_residence else None,
            "country_of_residence": register_data.country_of_residence if register_data.country_of_residence else "Nigeria",
            "state_of_origin": register_data.state_of_origin if register_data.state_of_origin else None,
            "local_government_origin": register_data.local_government_origin if register_data.local_government_origin else None,
            "rank": register_data.rank.strip(),
            "position": register_data.position if register_data.position else None,
            "years_of_service": register_data.years_of_service,
            "service_number": register_data.service_number if register_data.service_number else officer_id,
            "religion": register_data.religion,
            "additional_skills": register_data.additional_skills,
            "bank_name": register_data.bank_name,
            "account_number": register_data.account_number,
            "status": 'pending',
            "is_verified": False,
            "is_active": True,
            "created_by": created_by,
            # Add category field to track officer type
            "category": parsed_id['category'],
            # NEW: Initialize document fields for 2-upload system
            "passport_uploaded": False,
            "consolidated_pdf_uploaded": False
        }
        
        # 7. Create new officer record
        officer = ExistingOfficer(**officer_data)
        
        try:
            db.add(officer)
            db.commit()
            db.refresh(officer)
            logger.info(f"""
            ✅ {parsed_id['category']} Officer Registered Successfully:
               - ID: {officer_id}
               - Name: {register_data.full_name}
               - Email: {email}
               - Category: {parsed_id['category']}
               - Enlistment: {register_data.date_of_enlistment}
               - Promotion: {register_data.date_of_promotion or 'N/A'}
               - Registration ID: {officer.id}
               - Document System: 2-upload (passport + consolidated PDF)
            """)
            return officer
        except Exception as e:
            db.rollback()
            logger.error(f"Error registering existing officer: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register officer: {str(e)}"
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
        
        query = query.order_by(ExistingOfficer.created_at.desc())
        
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_dashboard_data(db: Session, officer_id: str) -> Dict[str, Any]:
        """Get dashboard data for existing officer - UPDATED FOR 2-UPLOAD SYSTEM"""
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        # Update dashboard access tracking
        officer.dashboard_access_count = (officer.dashboard_access_count or 0) + 1
        officer.last_dashboard_access = datetime.utcnow()
        db.commit()
        
        # Calculate document completion
        documents_uploaded = 0
        if officer.passport_uploaded:
            documents_uploaded += 1
        if officer.consolidated_pdf_uploaded:
            documents_uploaded += 1
        
        documents_completed = (documents_uploaded == 2)  # Both required
        
        # Prepare dashboard data for 2-upload system
        dashboard_data = {
            "officer_id": officer.officer_id,
            "full_name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "rank": officer.rank,
            "position": officer.position,
            "status": officer.status,
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "date_of_enlistment": officer.date_of_enlistment,
            "date_of_promotion": officer.date_of_promotion,
            "category": officer.category,
            
            # NEW: Simplified document status (only 2 uploads)
            "passport_uploaded": officer.passport_uploaded,
            "consolidated_pdf_uploaded": officer.consolidated_pdf_uploaded,
            
            # Document completion status
            "documents_completed": documents_completed,
            "documents_required": 2,
            "documents_uploaded": documents_uploaded,
            
            # PDF availability
            "has_terms_pdf": bool(officer.terms_pdf_path),
            "has_registration_pdf": bool(officer.registration_pdf_path),
            
            # Document paths for download
            "document_paths": {
                "passport": officer.passport_path,
                "consolidated_pdf": officer.consolidated_pdf_path,
            },
            
            # PDF paths for download
            "pdf_paths": {
                "terms": officer.terms_pdf_path,
                "registration": officer.registration_pdf_path,
            },
            
            # Timestamps
            "created_at": officer.created_at,
            "last_login": officer.last_login,
            "last_dashboard_access": officer.last_dashboard_access,
            "dashboard_access_count": officer.dashboard_access_count,
        }
        
        return dashboard_data
    
    @staticmethod
    def update_pdf_paths(
        db: Session,
        officer_id: str,
        terms_pdf_path: Optional[str] = None,
        registration_pdf_path: Optional[str] = None
    ) -> ExistingOfficer:
        """Update PDF paths for existing officer"""
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Officer not found"
            )
        
        if terms_pdf_path:
            officer.terms_pdf_path = terms_pdf_path
            officer.terms_generated_at = datetime.utcnow()
        
        if registration_pdf_path:
            officer.registration_pdf_path = registration_pdf_path
            officer.registration_generated_at = datetime.utcnow()
        
        officer.updated_at = datetime.utcnow()
        
        try:
            db.commit()
            db.refresh(officer)
            return officer
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating PDF paths: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update PDF paths"
            )