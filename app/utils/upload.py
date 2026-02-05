import os
from fastapi import UploadFile, HTTPException
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)
UPLOAD_DIR = "static/uploads"

# Allowed file types and sizes
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def normalize_officer_id(officer_id: str) -> str:
    """
    Normalize officer ID for file paths (replace / with -)
    
    Example: "MCN/001B/001" → "MCN-001B-001"
    """
    return officer_id.replace("/", "-").replace("\\", "-")


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file"""
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size {file_size/1024/1024:.2f}MB exceeds maximum size of {MAX_FILE_SIZE/1024/1024}MB"
        )


def save_upload(file: UploadFile, subfolder: str) -> str:
    """
    Save uploaded file to the appropriate subfolder.
    
    Args:
        file: UploadFile object
        subfolder: Subfolder within uploads directory (e.g., 'officers', 'applicants', 'existing_officers')
    
    Returns:
        Relative file path stored in database
    """
    # Validate file
    validate_file(file)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{uuid4().hex}{file_ext}"
    folder_path = os.path.join(UPLOAD_DIR, subfolder)

    # Create directory if it doesn't exist
    os.makedirs(folder_path, exist_ok=True)

    # Save file
    file_path = os.path.join(folder_path, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            # Read file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            while chunk := file.file.read(chunk_size):
                buffer.write(chunk)
        
        # Return relative path for database storage
        relative_path = os.path.join(subfolder, filename).replace("\\", "/")
        logger.info(f"✅ File uploaded successfully: {relative_path}")
        return relative_path
        
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )


def delete_file(file_path: str) -> bool:
    """
    Delete a file from the uploads directory.
    
    Args:
        file_path: Relative file path stored in database
    
    Returns:
        True if file was deleted, False otherwise
    """
    if not file_path:
        return False
    
    full_path = os.path.join(UPLOAD_DIR, file_path)
    
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"File deleted: {full_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting file {full_path}: {str(e)}")
        return False


def get_file_url(file_path: str, request) -> str:
    """
    Get full URL for a file.
    
    Args:
        file_path: Relative file path stored in database
        request: FastAPI Request object
    
    Returns:
        Full URL to access the file
    """
    if not file_path:
        return None
    
    base_url = str(request.base_url)
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    
    return f"{base_url}/static/{file_path}"