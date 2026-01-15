# app/services/existing_officer_service.py
import logging
import json
import re
from datetime import datetime
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
    """Validate and parse officer IDs"""
    
    # Officer categories based on ID prefix - CORRECTED: MCN, MBT, MBC only
    OFFICER_CATEGORIES = {
        'MCN': 'Marshal Core Nigeria',
        'MBT': 'Marshal Board of Trustees', 
        'MBC': 'Marshal Board Committee'
    }
    
    @staticmethod
    def validate_officer_id_format(officer_id: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Validate officer ID format and extract components
        Format: PREFIX/SEQUENCE/YEAR  e.g., MCN/001/2024
        Returns: (is_valid, error_message, parsed_data)
        """
        if not officer_id:
            return False, "Officer ID is required", None
        
        officer_id = officer_id.strip().upper()
        
        # Pattern: 2-4 letters / 1-4 digits / 4 digits
        pattern = r'^([A-Z]{2,4})/(\d{1,4})/(\d{4})$'
        match = re.match(pattern, officer_id)
        
        if not match:
            return False, "Invalid ID format. Use: PREFIX/NUMBER/YEAR (e.g., MCN/001/2024)", None
        
        prefix, sequence, year = match.groups()
        
        # Check if prefix is valid - CORRECTED: MCN, MBT, MBC only
        if prefix not in OfficerIDValidator.OFFICER_CATEGORIES:
            valid_prefixes = ', '.join(OfficerIDValidator.OFFICER_CATEGORIES.keys())
            return False, f"Invalid prefix '{prefix}'. Valid prefixes: {valid_prefixes}", None
        
        # Validate year
        current_year = datetime.now().year
        year_int = int(year)
        if year_int < 2000 or year_int > current_year:
            return False, f"Invalid year {year}. Must be between 2000 and {current_year}", None
        
        # Validate sequence number
        sequence_int = int(sequence)
        if sequence_int <= 0:
            return False, "Sequence number must be positive", None
        
        parsed_data = {
            'original_id': officer_id,
            'prefix': prefix,
            'sequence': sequence_int,
            'year': year_int,
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
    def generate_officer_id(prefix: str, sequence: int, year: int) -> str:
        """Generate a properly formatted officer ID"""
        if prefix not in OfficerIDValidator.OFFICER_CATEGORIES:
            raise ValueError(f"Invalid prefix. Must be one of: {list(OfficerIDValidator.OFFICER_CATEGORIES.keys())}")
        
        return f"{prefix}/{sequence:03d}/{year}"


# Mock verification service
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
        
        # 2. Validate officer ID format
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
            "sequence": parsed_id['sequence'],
            "year": parsed_id['year'],
            "full_name": f"Verified {parsed_id['category']} Officer",
            "message": f"{parsed_id['category']} officer credentials verified successfully"
        }
        
        # 5. Log verification details
        logger.info(f"""
        ✅ Officer Verification Successful:
           - ID: {officer_id}
           - Category: {parsed_id['category']}
           - Email: {email}
           - Prefix: {parsed_id['prefix']}
           - Sequence: {parsed_id['sequence']}
           - Year: {parsed_id['year']}
        """)
        
        return officer_data


class ExistingOfficerService:
    """Service for managing existing officers"""
    
    @staticmethod
    def verify_officer(
        db: Session, 
        verify_data: ExistingOfficerVerify
    ) -> Dict[str, Any]:
        """Verify officer credentials with enhanced validation"""
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
        
        # 2. Validate officer ID format
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
        """Register a new existing officer with enhanced validation"""
        logger.info(f"Registering existing officer: {register_data.officer_id}")
        
        # Clean and validate input
        officer_id = register_data.officer_id.strip().upper()
        email = register_data.email.strip().lower()
        phone = register_data.phone.strip()
        
        # 1. Validate officer ID format
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
        
        # 3. Check for duplicates
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
        
        # 4. Validate password length
        if len(register_data.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # 5. Prepare the data for creation
        officer_data = {
            "officer_id": officer_id,
            "email": email,
            "phone": phone,
            "password_hash": hash_password(register_data.password),
            "full_name": register_data.full_name.strip(),
            "nin_number": register_data.nin_number.strip(),
            "gender": register_data.gender if register_data.gender else "Not Specified",
            "date_of_birth": register_data.date_of_birth,
            "place_of_birth": register_data.place_of_birth.strip() if register_data.place_of_birth else "Not Specified",
            "nationality": register_data.nationality.strip() if register_data.nationality else "Nigerian",
            "marital_status": register_data.marital_status if register_data.marital_status else "Not Specified",
            "residential_address": register_data.residential_address.strip(),
            "state_of_residence": register_data.state_of_residence if register_data.state_of_residence else "Not Specified",
            "local_government_residence": register_data.local_government_residence if register_data.local_government_residence else "Not Specified",
            "country_of_residence": register_data.country_of_residence if register_data.country_of_residence else "Nigeria",
            "state_of_origin": register_data.state_of_origin if register_data.state_of_origin else "Not Specified",
            "local_government_origin": register_data.local_government_origin if register_data.local_government_origin else "Not Specified",
            "rank": register_data.rank.strip(),
            "position": register_data.position.strip() if register_data.position else "Not Specified",
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
            "category": parsed_id['category']
        }
        
        # 6. Create new officer record
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
               - Registration ID: {officer.id}
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
        
        # Validate file size (max 10MB)
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds 10MB limit"
            )
        
        # Validate file type
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
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
                try:
                    docs_list = json.loads(current_docs)
                    docs_list.append({
                        "type": document_type,
                        "path": file_path,
                        "description": description,
                        "uploaded_at": datetime.utcnow().isoformat()
                    })
                    officer.other_documents = json.dumps(docs_list)
                except json.JSONDecodeError:
                    docs_list = [{
                        "type": document_type,
                        "path": file_path,
                        "description": description,
                        "uploaded_at": datetime.utcnow().isoformat()
                    }]
                    officer.other_documents = json.dumps(docs_list)
            
            officer.updated_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Document uploaded successfully: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}", exc_info=True)
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
        
        query = query.order_by(ExistingOfficer.created_at.desc())
        
        return query.offset(skip).limit(limit).all()