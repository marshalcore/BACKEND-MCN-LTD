# app/utils/pdf_compression.py
import os
import logging
from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import PyPDF2
from io import BytesIO

logger = logging.getLogger(__name__)

# Target sizes
TARGET_PDF_SIZE = 1 * 1024 * 1024  # 1MB
MAX_PDF_SIZE = 2 * 1024 * 1024  # 2MB absolute max

def get_pdf_size(pdf_path: Path) -> int:
    """Get PDF file size in bytes"""
    try:
        return os.path.getsize(pdf_path)
    except:
        return 0

def is_pdf_under_limit(pdf_path: Path, limit: int = TARGET_PDF_SIZE) -> bool:
    """Check if PDF is under size limit"""
    size = get_pdf_size(pdf_path)
    return size <= limit

def compress_pdf_with_pypdf2(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Compress PDF using PyPDF2 (basic compression)
    """
    if output_path is None:
        output_path = input_path.with_stem(f"{input_path.stem}_compressed")
    
    try:
        reader = PyPDF2.PdfReader(str(input_path))
        writer = PyPDF2.PdfWriter()
        
        # Copy all pages
        for page_num in range(len(reader.pages)):
            writer.add_page(reader.pages[page_num])
        
        # Compress
        for page in writer.pages:
            page.compress_content_streams()
        
        # Write to output
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        logger.info(f"✅ PDF compressed: {output_path.name} - {get_pdf_size(output_path)/1024:.2f}KB")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ PDF compression failed: {str(e)}")
        return input_path  # Return original on failure

def compress_pdf_quality_reduction(input_path: Path, output_path: Optional[Path] = None, quality: int = 50) -> Path:
    """
    Compress PDF by reducing image quality (requires additional libraries)
    This is a placeholder - would need pikepdf or similar
    """
    logger.warning("Advanced PDF compression requires pikepdf library")
    logger.info("Install with: pip install pikepdf")
    return input_path

def should_compress(pdf_path: Path, threshold: int = TARGET_PDF_SIZE) -> bool:
    """Determine if PDF needs compression"""
    size = get_pdf_size(pdf_path)
    return size > threshold

def get_compression_ratio(pdf_path: Path) -> float:
    """Get compression ratio needed"""
    size = get_pdf_size(pdf_path)
    if size <= TARGET_PDF_SIZE:
        return 1.0
    return TARGET_PDF_SIZE / size