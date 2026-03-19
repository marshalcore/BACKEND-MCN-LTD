# app/utils/__init__.py - UPDATED WITH NEW UTILITIES
from .hash import hash_password, verify_password
from .jwt_handler import create_access_token, decode_token, verify_token
from .email_validator import validate_email, EmailValidator
from .upload import save_upload, validate_file, delete_file, get_file_url, normalize_officer_id
from .image_processing import (
    validate_image_file,
    validate_image_count,
    read_image_file,
    get_image_dimensions,
    calculate_target_size,
    normalize_filename
)
from .pdf_compression import (
    compress_pdf_with_pypdf2,
    is_pdf_under_limit,
    should_compress,
    get_pdf_size
)
from .file_naming import (
    generate_pdf_filename,
    sanitize_filename,
    create_dated_folder
)

__all__ = [
    # Auth utilities
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "verify_token",
    
    # Email validation
    "validate_email",
    "EmailValidator",
    
    # Upload utilities
    "save_upload",
    "validate_file",
    "delete_file",
    "get_file_url",
    "normalize_officer_id",
    
    # Image processing utilities (NEW)
    "validate_image_file",
    "validate_image_count",
    "read_image_file",
    "get_image_dimensions",
    "calculate_target_size",
    "normalize_filename",
    
    # PDF compression utilities (NEW)
    "compress_pdf_with_pypdf2",
    "is_pdf_under_limit",
    "should_compress",
    "get_pdf_size",
    
    # File naming utilities (NEW)
    "generate_pdf_filename",
    "sanitize_filename",
    "create_dated_folder",
]