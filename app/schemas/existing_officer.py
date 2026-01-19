from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from uuid import UUID
import re
import logging

logger = logging.getLogger(__name__)


class ExistingOfficerVerify(BaseModel):
    """Schema for verifying existing officer credentials - UPDATED FORMAT"""
    officer_id: str = Field(..., min_length=8, max_length=50, description="Officer ID in format: PREFIX/ALPHANUMERIC/INTAKE (e.g., MCN/001B/031)")
    email: EmailStr = Field(..., description="Officer email address")
    
    @validator('officer_id')
    def validate_officer_id_format(cls, v):
        """Validate NEW officer ID format: PREFIX/ALPHANUMERIC/INTAKE"""
        v = v.strip().upper()
        
        # NEW Pattern: MCN|MBT|MBC / 3-4 alphanumeric / 3 digits
        pattern = r'^(MCN|MBT|MBC)/[A-Z0-9]{3,4}/\d{3}$'
        
        if not re.match(pattern, v):
            raise ValueError('Invalid ID format. Use: PREFIX/ALPHANUMERIC/INTAKE (e.g., MCN/001B/031)')
        
        # Check valid prefixes: MCN, MBT, MBC only
        valid_prefixes = ['MCN', 'MBT', 'MBC']
        prefix = v.split('/')[0]
        if prefix not in valid_prefixes:
            raise ValueError(f'Invalid prefix "{prefix}". Valid prefixes: {", ".join(valid_prefixes)}')
        
        return v
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Enhanced email domain validation - blocks disposable emails"""
        v = v.strip().lower()
        
        # Get disposable domains from URL content
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'mailinator.com',
            'yopmail.com', 'throwawaymail.com', 'trashmail.com',
            'dispostable.com', 'maildrop.cc', 'guerrillamail.com',
            'sharklasers.com', 'maildrop.cc'
        ]
        
        if '@' in v:
            domain = v.split('@')[1]
            
            # Check against disposable domains
            for disposable in disposable_domains:
                if disposable in domain:
                    raise ValueError('Disposable/temporary email addresses are not allowed. Please use a professional email.')
            
            # Additional professional email validation
            if domain.endswith('.temp') or domain.endswith('.xyz'):
                raise ValueError('Please use a professional email address from a recognized provider.')
        
        return v


class ExistingOfficerRegister(BaseModel):
    """Schema for registering an existing officer - UPDATED WITH NEW FIELDS"""
    # Credentials
    officer_id: str = Field(..., min_length=8, max_length=50)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)
    
    # NEW REQUIRED FIELDS
    date_of_enlistment: date = Field(..., description="Date officer enlisted (YYYY-MM-DD)")
    date_of_promotion: Optional[date] = Field(None, description="Date of last promotion (YYYY-MM-DD)")
    
    # Personal Information
    full_name: str = Field(..., min_length=2, max_length=100)
    nin_number: str = Field(..., min_length=10, max_length=20)
    gender: str = Field(..., max_length=10)
    date_of_birth: date
    place_of_birth: Optional[str] = Field(None, max_length=100)
    nationality: Optional[str] = Field(None, max_length=50)
    marital_status: Optional[str] = Field(None, max_length=20)
    
    # Contact Information
    residential_address: str = Field(..., max_length=500)
    state_of_residence: Optional[str] = Field(None, max_length=50)
    local_government_residence: Optional[str] = Field(None, max_length=50)
    country_of_residence: Optional[str] = Field(None, max_length=50)
    
    # Origin Information
    state_of_origin: Optional[str] = Field(None, max_length=50)
    local_government_origin: Optional[str] = Field(None, max_length=50)
    
    # Professional Information
    rank: str = Field(..., max_length=50)
    position: Optional[str] = Field(None, max_length=100)
    years_of_service: Optional[str] = Field(None, max_length=20)
    service_number: Optional[str] = Field(None, max_length=50)
    
    # Additional Information
    religion: Optional[str] = Field(None, max_length=30)
    additional_skills: Optional[str] = Field(None, max_length=1000)
    
    # Financial Information
    bank_name: Optional[str] = Field(None, max_length=100)
    account_number: Optional[str] = Field(None, max_length=20)
    
    @validator('officer_id')
    def validate_officer_id(cls, v):
        """Validate NEW officer ID format during registration"""
        v = v.strip().upper()
        # NEW Pattern: MCN|MBT|MBC / 3-4 alphanumeric / 3 digits
        pattern = r'^(MCN|MBT|MBC)/[A-Z0-9]{3,4}/\d{3}$'
        
        if not re.match(pattern, v):
            raise ValueError('Invalid ID format. Use: PREFIX/ALPHANUMERIC/INTAKE (e.g., MCN/001B/031)')
        
        # Check valid prefixes
        valid_prefixes = ['MCN', 'MBT', 'MBC']
        prefix = v.split('/')[0]
        if prefix not in valid_prefixes:
            raise ValueError(f'Invalid prefix "{prefix}". Valid prefixes: {", ".join(valid_prefixes)}')
        
        return v
    
    @validator('date_of_enlistment')
    def validate_enlistment_date(cls, v):
        """Validate date of enlistment is not in future"""
        if v > date.today():
            raise ValueError('Date of enlistment cannot be in the future')
        return v
    
    @validator('date_of_promotion')
    def validate_promotion_date(cls, v, values):
        """Validate promotion date is after enlistment date if provided"""
        if v and 'date_of_enlistment' in values and values['date_of_enlistment']:
            if v < values['date_of_enlistment']:
                raise ValueError('Date of promotion must be after date of enlistment')
            if v > date.today():
                raise ValueError('Date of promotion cannot be in the future')
        return v
    
    @validator('phone')
    def validate_phone_number(cls, v):
        """Validate Nigerian phone numbers"""
        v = v.strip()
        
        # Remove any non-digit characters
        digits = ''.join(filter(str.isdigit, v))
        
        # Nigerian phone numbers: +234XXXXXXXXXX or 0XXXXXXXXXX
        if not (10 <= len(digits) <= 13):
            raise ValueError('Invalid phone number length')
        
        # Check if it starts with Nigerian country code or 0
        if digits.startswith('234'):
            if len(digits) != 13:
                raise ValueError('Invalid Nigerian number with country code')
        elif digits.startswith('0'):
            if len(digits) != 11:
                raise ValueError('Invalid Nigerian number')
        else:
            raise ValueError('Phone number must start with +234 or 0')
        
        return v
    
    @validator('email')
    def validate_officer_email(cls, v):
        """Enhanced email validation for officers"""
        v = v.strip().lower()
        
        # Get disposable domains from URL content
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'mailinator.com',
            'yopmail.com', 'throwawaymail.com', 'trashmail.com',
            'dispostable.com', 'maildrop.cc', 'guerrillamail.com',
            'sharklasers.com'
        ]
        
        if '@' in v:
            domain = v.split('@')[1]
            
            for disposable in disposable_domains:
                if disposable in domain:
                    raise ValueError('Professional email addresses required. Disposable/temporary emails are not allowed for officer registration.')
            
            # Check for professional domains
            professional_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
            if not any(domain.endswith(prof_domain) for prof_domain in professional_domains):
                logger.warning(f"Non-standard email domain used: {domain}")
        
        return v
    
    @validator('place_of_birth', 'nationality', 'marital_status', 'state_of_residence',
               'local_government_residence', 'country_of_residence', 'state_of_origin',
               'local_government_origin', 'religion', 'position', 'years_of_service',
               'service_number', 'additional_skills', 'bank_name', 'account_number')
    def convert_empty_to_none(cls, v):
        """Convert empty strings to None for optional fields"""
        if isinstance(v, str):
            v = v.strip()
            if v == "" or v == "Select Marital Status" or v == "Select Religion":
                return None
        return v
    
    @validator('nationality')
    def set_default_nationality(cls, v):
        """Set default nationality if empty"""
        if not v:
            return "Nigerian"
        return v
    
    @validator('country_of_residence')
    def set_default_country(cls, v):
        """Set default country if empty"""
        if not v:
            return "Nigeria"
        return v


class ExistingOfficerDocument(BaseModel):
    """Schema for document upload metadata - UPDATED FOR 2-UPLOAD SYSTEM"""
    document_type: str = Field(
        ...,
        description="Type of document being uploaded: 'passport' or 'consolidated_pdf' only"
    )
    description: Optional[str] = Field(None, max_length=200)


class ExistingOfficerResponse(BaseModel):
    """Response schema for existing officer data"""
    id: UUID
    officer_id: str
    email: EmailStr
    phone: str
    status: str
    is_verified: bool
    is_active: bool
    full_name: str
    nin_number: str
    rank: str
    position: Optional[str]
    category: Optional[str]
    # NEW FIELDS
    date_of_enlistment: date  # ✅ CHANGED: Not Optional (required)
    date_of_promotion: Optional[date]
    # NEW: Simplified document status
    passport_uploaded: bool
    consolidated_pdf_uploaded: bool
    created_at: datetime
    updated_at: Optional[datetime]
    verification_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class ExistingOfficerDetailResponse(ExistingOfficerResponse):
    """Detailed response schema for existing officer"""
    gender: str
    date_of_birth: date
    place_of_birth: Optional[str]
    nationality: Optional[str]
    marital_status: Optional[str]
    residential_address: str
    state_of_residence: Optional[str]
    local_government_residence: Optional[str]
    country_of_residence: Optional[str]
    state_of_origin: Optional[str]
    local_government_origin: Optional[str]
    years_of_service: Optional[str]
    service_number: Optional[str]
    religion: Optional[str]
    additional_skills: Optional[str]
    bank_name: Optional[str]
    account_number: Optional[str]
    last_login: Optional[datetime]
    admin_notes: Optional[str]
    rejection_reason: Optional[str]
    
    # NEW: Simplified document paths (only 2 uploads)
    passport_path: Optional[str]
    consolidated_pdf_path: Optional[str]
    
    # PDF paths
    terms_pdf_path: Optional[str]
    registration_pdf_path: Optional[str]


class ExistingOfficerUpdate(BaseModel):
    """Schema for updating existing officer status (admin only)"""
    status: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    admin_notes: Optional[str] = Field(None, max_length=1000)
    rejection_reason: Optional[str] = Field(None, max_length=1000)


class ExistingOfficerLogin(BaseModel):
    """Schema for existing officer login"""
    officer_id: str = Field(..., min_length=8, max_length=50)
    password: str = Field(..., min_length=8)


class VerifyResponse(BaseModel):
    """Response for verification endpoint - ENHANCED"""
    verified: bool
    message: str
    officer_data: Optional[dict] = None
    category: Optional[str] = None
    id_details: Optional[dict] = None


class RegisterResponse(BaseModel):
    """Response for registration endpoint - ENHANCED"""
    status: str
    message: str
    officer_id: str
    email: str
    category: Optional[str] = None
    next_steps: List[str] = Field(default_factory=list)
    registration_id: Optional[str] = None
    # NEW: Include dates in response
    date_of_enlistment: date  # ✅ CHANGED: Not Optional (required)
    date_of_promotion: Optional[date] = None
    # NEW: Document upload instructions
    upload_instructions: List[str] = Field(default_factory=lambda: [
        "1. Upload Passport Photo (JPG/PNG, 2MB max)",
        "2. Upload Consolidated PDF with all 10 documents (10MB max)",
        "3. PDFs will be auto-generated and emailed to you"
    ])


# Schema for dashboard data - UPDATED FOR 2-UPLOAD SYSTEM
class ExistingOfficerDashboard(BaseModel):
    """Schema for existing officer dashboard data - UPDATED FOR 2-UPLOAD SYSTEM"""
    officer_id: str
    full_name: str
    email: str
    phone: str
    rank: str
    position: Optional[str]
    status: str
    is_verified: bool
    is_active: bool
    date_of_enlistment: date  # ✅ CHANGED: Not Optional (required)
    date_of_promotion: Optional[date]
    category: Optional[str]
    
    # NEW: Simplified document status (only 2 uploads)
    passport_uploaded: bool
    consolidated_pdf_uploaded: bool
    
    # Document completion status
    documents_completed: bool = Field(default=False)
    documents_required: int = Field(default=2)
    documents_uploaded: int = Field(default=0)
    
    # PDF availability
    has_terms_pdf: bool
    has_registration_pdf: bool
    
    # Document paths for download
    document_paths: dict = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


# Schema for document upload response
class DocumentUploadResponse(BaseModel):
    """Response for document upload - UPDATED FOR 2-UPLOAD SYSTEM"""
    status: str
    message: str
    document_type: str
    officer_id: str
    file_path: str
    is_required: bool
    upload_complete: bool = Field(default=False)
    remaining_uploads: List[str] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# Schema for PDF generation response
class PDFGenerationResponse(BaseModel):
    """Response for PDF generation"""
    status: str
    message: str
    officer_id: str
    email: str
    terms_pdf_path: Optional[str] = None
    registration_pdf_path: Optional[str] = None
    email_sent: bool = Field(default=False)
    download_urls: dict = Field(default_factory=dict)
    
    class Config:
        from_attributes = True