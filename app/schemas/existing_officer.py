# app/schemas/existing_officer.py
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
from uuid import UUID
import re


class ExistingOfficerVerify(BaseModel):
    """Schema for verifying existing officer credentials"""
    officer_id: str = Field(..., min_length=3, max_length=50, description="Officer ID in format: PREFIX/NUMBER/YEAR (e.g., MCN/001/2024)")
    email: EmailStr = Field(..., description="Officer email address")
    
    @validator('officer_id')
    def validate_officer_id_format(cls, v):
        """Validate officer ID format with slashes"""
        v = v.strip().upper()
        
        # Pattern: 2-4 letters / 1-4 digits / 4 digits
        pattern = r'^([A-Z]{2,4})/(\d{1,4})/(\d{4})$'
        
        if not re.match(pattern, v):
            raise ValueError('Invalid ID format. Use: PREFIX/NUMBER/YEAR (e.g., MCN/001/2024)')
        
        # Check valid prefixes: MCN, MBT, MBC only
        valid_prefixes = ['MCN', 'MBT', 'MBC']
        prefix = v.split('/')[0]
        if prefix not in valid_prefixes:
            raise ValueError(f'Invalid prefix "{prefix}". Valid prefixes: {", ".join(valid_prefixes)}')
        
        # Validate year
        from datetime import datetime
        current_year = datetime.now().year
        year = int(v.split('/')[2])
        
        if year < 2000 or year > current_year:
            raise ValueError(f'Invalid year {year}. Must be between 2000 and {current_year}')
        
        return v
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Basic email domain validation"""
        v = v.strip().lower()
        
        # Check for common disposable domains
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'mailinator.com',
            'yopmail.com', 'throwawaymail.com', 'trashmail.com',
            'dispostable.com', 'maildrop.cc', 'guerrillamail.com'
        ]
        
        domain = v.split('@')[1] if '@' in v else ''
        
        for disposable in disposable_domains:
            if disposable in domain:
                raise ValueError('Disposable email addresses are not allowed')
        
        return v


class ExistingOfficerRegister(BaseModel):
    """Schema for registering an existing officer"""
    # Credentials
    officer_id: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8)
    
    # Personal Information
    full_name: str = Field(..., min_length=2, max_length=100)
    nin_number: str = Field(..., min_length=10, max_length=20)
    gender: str = Field(..., max_length=10)
    date_of_birth: date
    place_of_birth: Optional[str] = Field(None, max_length=100)
    nationality: str = Field(default="Nigerian", max_length=50)
    marital_status: Optional[str] = Field(None, max_length=20)
    
    # Contact Information
    residential_address: str = Field(..., max_length=500)
    state_of_residence: Optional[str] = Field(None, max_length=50)
    local_government_residence: Optional[str] = Field(None, max_length=50)
    country_of_residence: str = Field(default="Nigeria", max_length=50)
    
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
        """Validate officer ID during registration"""
        v = v.strip().upper()
        pattern = r'^([A-Z]{2,4})/(\d{1,4})/(\d{4})$'
        
        if not re.match(pattern, v):
            raise ValueError('Invalid ID format. Use: PREFIX/NUMBER/YEAR (e.g., MCN/001/2024)')
        
        # Check valid prefixes
        valid_prefixes = ['MCN', 'MBT', 'MBC']
        prefix = v.split('/')[0]
        if prefix not in valid_prefixes:
            raise ValueError(f'Invalid prefix "{prefix}". Valid prefixes: {", ".join(valid_prefixes)}')
        
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
        """Additional email validation for officers"""
        v = v.strip().lower()
        
        # Check against disposable domains
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'mailinator.com',
            'yopmail.com', 'throwawaymail.com', 'trashmail.com'
        ]
        
        domain = v.split('@')[1] if '@' in v else ''
        
        for disposable in disposable_domains:
            if disposable in domain:
                raise ValueError('Professional email addresses required. Disposable emails not allowed.')
        
        return v


class ExistingOfficerDocument(BaseModel):
    """Schema for document upload metadata"""
    document_type: str = Field(
        ...,
        description="Type of document being uploaded"
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
    category: Optional[str]  # Added category field
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
    nationality: str
    marital_status: Optional[str]
    residential_address: str
    state_of_residence: Optional[str]
    local_government_residence: Optional[str]
    country_of_residence: str
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
    
    # Document paths
    passport_photo: Optional[str]
    nin_slip: Optional[str]
    ssce_certificate: Optional[str]
    birth_certificate: Optional[str]
    letter_of_first_appointment: Optional[str]
    promotion_letters: Optional[str]
    service_certificate: Optional[str]
    medical_certificate: Optional[str]
    guarantor_form: Optional[str]
    other_documents: Optional[str]


class ExistingOfficerUpdate(BaseModel):
    """Schema for updating existing officer status (admin only)"""
    status: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    admin_notes: Optional[str] = Field(None, max_length=1000)
    rejection_reason: Optional[str] = Field(None, max_length=1000)


class ExistingOfficerLogin(BaseModel):
    """Schema for existing officer login"""
    officer_id: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class VerifyResponse(BaseModel):
    """Response for verification endpoint - ENHANCED"""
    verified: bool
    message: str
    officer_data: Optional[dict] = None
    category: Optional[str] = None  # Added category
    id_details: Optional[dict] = None  # Added ID details


class RegisterResponse(BaseModel):
    """Response for registration endpoint - ENHANCED"""
    status: str
    message: str
    officer_id: str
    email: str
    category: Optional[str] = None  # Added category
    next_steps: List[str] = Field(default_factory=list)
    registration_id: Optional[str] = None