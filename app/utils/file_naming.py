# app/utils/file_naming.py
import os
import uuid
from datetime import datetime
import re
from typing import Optional

def generate_pdf_filename(
    email: str,
    num_images: int,
    officer_id: Optional[str] = None,
    prefix: str = "officer_docs"
) -> str:
    """
    Generate unique filename for PDF
    
    Format: prefix_email_part_officer_part_timestamp_uniqueid.pdf
    """
    # Sanitize email
    email_part = email.split('@')[0].replace('.', '_').replace('-', '_')
    
    # Sanitize officer ID if provided
    officer_part = ""
    if officer_id:
        # ✅ FIXED: Replace slashes and backslashes separately (can't use \ inside f-string)
        temp_id = officer_id.replace('/', '-')
        temp_id = temp_id.replace('\\', '-')
        temp_id = temp_id.replace(' ', '_')
        officer_part = f"_{temp_id}"
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Generate unique ID
    unique_id = str(uuid.uuid4())[:8]
    
    # Combine parts
    filename = f"{prefix}_{email_part}{officer_part}_{timestamp}_{unique_id}.pdf"
    
    return filename

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other issues
    """
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove any control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove any other problematic characters
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Limit length
    if len(filename) > 100:
        name, ext = os.path.splitext(filename)
        filename = name[:90] + ext
    
    return filename

def extract_email_from_filename(filename: str) -> Optional[str]:
    """
    Extract email from filename (reverse of generate_pdf_filename)
    """
    try:
        # Format: prefix_email_part_officer_part_timestamp_uniqueid.pdf
        parts = filename.split('_')
        if len(parts) >= 3:
            # The email part is the second part after prefix
            # This is approximate - exact extraction depends on format
            return parts[1].replace('_', '.') + '@example.com'  # Placeholder
        return None
    except:
        return None

def create_dated_folder(base_path: str, date: Optional[datetime] = None) -> str:
    """
    Create dated folder structure (year/month/day)
    """
    if date is None:
        date = datetime.now()
    
    year = date.strftime("%Y")
    month = date.strftime("%m")
    day = date.strftime("%d")
    
    folder_path = os.path.join(base_path, year, month, day)
    os.makedirs(folder_path, exist_ok=True)
    
    return folder_path