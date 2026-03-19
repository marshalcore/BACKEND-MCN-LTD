# app/utils/image_processing.py
import os
import logging
from typing import List, Tuple, Optional
from fastapi import UploadFile, HTTPException
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

# Allowed image types and sizes
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/jpg', 'image/png'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB per image
MAX_IMAGES_PER_UPLOAD = 5
MIN_IMAGES_PER_UPLOAD = 4

def validate_image_file(file: UploadFile) -> Tuple[bool, str]:
    """
    Validate an image file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check filename
    if not file.filename:
        return False, "No file name provided"
    
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, f"Invalid file extension {file_ext}. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
    
    # Check content type
    if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        return False, f"Invalid content type {file.content_type}. Allowed: image/jpeg, image/png"
    
    return True, ""

def validate_image_count(files: List[UploadFile]) -> Tuple[bool, str]:
    """
    Validate number of images (4-5)
    """
    if len(files) < MIN_IMAGES_PER_UPLOAD:
        return False, f"Minimum {MIN_IMAGES_PER_UPLOAD} images required. You uploaded {len(files)}."
    
    if len(files) > MAX_IMAGES_PER_UPLOAD:
        return False, f"Maximum {MAX_IMAGES_PER_UPLOAD} images allowed. You uploaded {len(files)}."
    
    return True, ""

async def read_image_file(file: UploadFile) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Read and validate image file size
    
    Returns:
        Tuple of (image_bytes, error_message)
    """
    try:
        # Read file
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_IMAGE_SIZE:
            size_mb = len(content) / (1024 * 1024)
            max_mb = MAX_IMAGE_SIZE / (1024 * 1024)
            return None, f"File size {size_mb:.2f}MB exceeds maximum of {max_mb}MB"
        
        # Quick validation that it's actually an image
        try:
            img = Image.open(BytesIO(content))
            img.verify()  # Verify it's a valid image
        except Exception as e:
            return None, f"Invalid image file: {str(e)}"
        
        return content, None
        
    except Exception as e:
        return None, f"Failed to read file: {str(e)}"

def get_image_dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """Get image dimensions without loading full image"""
    try:
        img = Image.open(BytesIO(image_bytes))
        return img.width, img.height
    except:
        return 0, 0

def calculate_target_size(original_size: int, target_size_kb: int = 160) -> Tuple[int, int]:
    """
    Calculate target dimensions for image resizing
    
    Args:
        original_size: Original file size in bytes
        target_size_kb: Target size in KB (default 160KB)
    
    Returns:
        Tuple of (max_width, max_height)
    """
    # Base dimensions for different quality levels
    if original_size < target_size_kb * 512:  # < 80KB
        return (1200, 1600)  # High quality
    elif original_size < target_size_kb * 1024:  # < 160KB
        return (1000, 1333)  # Medium quality
    else:
        return (800, 1066)  # Compressed quality

def normalize_filename(filename: str) -> str:
    """Normalize filename for safe storage"""
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    # Remove any other problematic characters
    import re
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    return filename