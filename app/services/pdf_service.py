import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
import uuid
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
PDFS_DIR = STATIC_DIR / "pdfs"
TERMS_DIR = PDFS_DIR / "terms"
APPLICATIONS_DIR = PDFS_DIR / "applications"
LOGO_DIR = STATIC_DIR / "images"
UPLOADS_DIR = STATIC_DIR / "uploads"

# Ensure directories exist
for directory in [PDFS_DIR, TERMS_DIR, APPLICATIONS_DIR, LOGO_DIR, UPLOADS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Company information
COMPANY_INFO = {
    "name": "Marshal Core of Nigeria",
    "certificate_number": "YA/CLB/10100",
    "rc_number": "8405988",
    "address_line1": "KM. 3, MARSHAL CORE OF NIGERIA NATIONAL HEADQUARTERS",
    "address_line2": "ABUMWENRENRE COMMUNITY, EKIADOLOR/AGEKPANU ROAD",
    "address_line3": "BENIN CITY, EDO STATE, NIGERIA",
    "phone": "+234 9137 428 031",
    "email": "info@marshalcoreofnigeria.ng",
    "website": "www.marshalcoreofnigeria.ng",
    "logo_path": str(LOGO_DIR / "logo.png")
}

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

class PDFGenerator:
    """PDF generation utility using ReportLab with passport photo embedding"""
    
    def __init__(self):
        """Initialize PDF generator"""
        logger.info("Initializing PDF Generator")
        self.logo_image = None
        self.logo_bytes = None
        self._load_logo()
    
    def _load_logo(self):
        """Load company logo"""
        try:
            logo_path = Path(COMPANY_INFO['logo_path'])
            
            if logo_path.exists():
                with open(logo_path, 'rb') as f:
                    self.logo_bytes = f.read()
                    self.logo_image = BytesIO(self.logo_bytes)
                logger.info("✅ Logo loaded successfully")
                return True
            
            # Try alternative locations
            possible_paths = [
                LOGO_DIR / "logo.png",
                STATIC_DIR / "logo.png",
                BASE_DIR / "static" / "images" / "logo.png",
                BASE_DIR / "static" / "logo.png",
                Path("/app/static/images/logo.png"),
            ]
            
            for path in possible_paths:
                if path.exists():
                    with open(path, 'rb') as f:
                        self.logo_bytes = f.read()
                        self.logo_image = BytesIO(self.logo_bytes)
                    logger.info(f"✅ Logo loaded from {path}")
                    return True
            
            logger.warning("⚠️ Logo file not found, using text placeholder")
            return False
                
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")
            return False
    
    def _resolve_passport_path(self, passport_path: str) -> Optional[Path]:
        """Resolve absolute path for passport photo"""
        if not passport_path:
            return None
        
        try:
            # Check if it's already an absolute path
            if os.path.isabs(passport_path):
                path = Path(passport_path)
                if path.exists():
                    return path
            
            # Try relative paths
            possible_paths = [
                Path(passport_path),
                UPLOADS_DIR / passport_path,
                STATIC_DIR / passport_path,
                BASE_DIR / passport_path,
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"✅ Found passport photo at: {path}")
                    return path
            
            logger.warning(f"Passport photo not found: {passport_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving passport path: {e}")
            return None
    
    def _prepare_passport_image(self, passport_path: str, width=1.5*inch, height=2*inch) -> Optional[Image]:
        """Prepare passport image for PDF embedding"""
        try:
            absolute_path = self._resolve_passport_path(passport_path)
            if not absolute_path:
                return None
            
            # Validate file size
            file_size = absolute_path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(f"Passport photo too large: {file_size} bytes")
                return None
            
            # Open and validate image
            pil_img = PILImage.open(absolute_path)
            
            # Convert RGBA to RGB if necessary
            if pil_img.mode in ('RGBA', 'LA', 'P'):
                if pil_img.mode == 'P':
                    pil_img = pil_img.convert('RGB')
                else:
                    # Create white background for transparent images
                    background = PILImage.new('RGB', pil_img.size, (255, 255, 255))
                    if pil_img.mode == 'RGBA':
                        background.paste(pil_img, mask=pil_img.split()[-1])
                    else:
                        background.paste(pil_img, mask=pil_img)
                    pil_img = background
            
            # Resize if necessary while maintaining aspect ratio
            max_width, max_height = 400, 400
            if pil_img.width > max_width or pil_img.height > max_height:
                pil_img.thumbnail((max_width, max_height), PILImage.Resampling.LANCZOS)
            
            # Save to bytes
            img_bytes = BytesIO()
            pil_img.save(img_bytes, format='JPEG', quality=85)
            img_bytes.seek(0)
            
            logger.info(f"✅ Passport photo prepared: {absolute_path}, size: {pil_img.size}")
            return Image(img_bytes, width=width, height=height)
            
        except Exception as e:
            logger.error(f"Error preparing passport image: {e}")
            return None
    
    def _generate_filename(self, user_id: str, document_type: str) -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, category: str, filename: str) -> Tuple[str, str]:
        """Get filepath for saving PDF"""
        category_dir = PDFS_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = category_dir / filename
        relative_path = f"static/pdfs/{category}/{filename}"
        
        return str(file_path), relative_path
    
    def _create_header_footer(self, canvas_obj, doc, title="", is_terms=False):
        """Create header and footer for PDF pages"""
        canvas_obj.saveState()
        
        # Add logo at top right
        if self.logo_image and self.logo_bytes:
            try:
                self.logo_image.seek(0)
                logo_width = 1.2 * inch
                logo_height = 0.6 * inch
                logo_x = doc.width + doc.leftMargin - logo_width - 0.2*inch
                logo_y = doc.height + doc.topMargin - 0.1*inch
                
                canvas_obj.drawImage(ImageReader(self.logo_image), logo_x, logo_y,
                                   width=logo_width, height=logo_height,
                                   mask='auto', preserveAspectRatio=True)
            except Exception as e:
                logger.warning(f"Could not draw logo: {e}")
        
        # Header text
        canvas_obj.setFont('Helvetica-Bold', 12)
        canvas_obj.setFillColor(colors.HexColor('#1a237e'))
        canvas_obj.drawString(doc.leftMargin, doc.height + doc.topMargin + 0.6*inch,
                            COMPANY_INFO['name'])
        
        # Address
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.gray)
        
        address_y = doc.height + doc.topMargin + 0.4*inch
        canvas_obj.drawString(doc.leftMargin, address_y, COMPANY_INFO['address_line1'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.15*inch, COMPANY_INFO['address_line2'])
        canvas_obj.drawString(doc.leftMargin, address_y - 0.3*inch, COMPANY_INFO['address_line3'])
        
        # Line under header
        canvas_obj.setStrokeColor(colors.HexColor('#1a237e'))
        canvas_obj.setLineWidth(1)
        canvas_obj.line(doc.leftMargin, doc.height + doc.topMargin + 0.1*inch,
                       doc.width + doc.leftMargin, doc.height + doc.topMargin + 0.1*inch)
        
        # Footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(colors.gray)
        
        # Page number
        canvas_obj.drawString(doc.leftMargin, 0.5*inch, f"Page {doc.page}")
        
        # Document info
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas_obj.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, doc_info)
        
        # Date
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas_obj.drawRightString(doc.width + doc.leftMargin, 0.5*inch, date_str)
        
        # Line above footer
        canvas_obj.setStrokeColor(colors.lightgrey)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(doc.leftMargin, 0.7*inch, doc.width + doc.leftMargin, 0.7*inch)
        
        canvas_obj.restoreState()
    
    def _format_date(self, date_value) -> str:
        """Format date for display"""
        if not date_value:
            return "N/A"
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime("%d %B, %Y")
        
        if isinstance(date_value, str):
            try:
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]:
                    try:
                        parsed_date = datetime.strptime(date_value, fmt)
                        return parsed_date.strftime("%d %B, %Y")
                    except:
                        continue
            except:
                pass
        
        return str(date_value)
    
    def generate_terms_conditions(self, user_data: Dict[str, Any], user_id: str) -> str:
        """Generate Terms & Conditions PDF"""
        try:
            logger.info(f"Generating Terms & Conditions PDF for user: {user_id}")
            
            filename = self._generate_filename(user_id, "terms")
            filepath, relative_path = self._save_pdf("terms", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Title'],
                fontSize=18,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=24,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                alignment=TA_JUSTIFY,
                fontName='Helvetica'
            )
            
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold'
            )
            
            # Title
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            # Document info
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-NG-{user_id}-{datetime.now().strftime('%Y%m%d')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Effective Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # IMPORTANT NOTICE
            story.append(Paragraph(
                "<b>IMPORTANT NOTICE:</b> This is a legally binding agreement between "
                "Marshal Core of Nigeria (hereinafter referred to as 'the Organization') "
                "and the Officer/Applicant (hereinafter referred to as 'the Officer'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            # 1. PARTIES TO THE AGREEMENT
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            
            # 1.1 The Organization
            story.append(Paragraph(
                f"<b>1.1 The Organization:</b> Marshal Core of Nigeria, a voluntary organization "
                "duly registered under ministry of humanitarian affairs with certificate number: "
                f"<b>{COMPANY_INFO['certificate_number']}</b>, and incorporated under the "
                "COMPANIES AND ALLIED MATTERS ACT 2020 Federal Republic of Nigeria with "
                f"RC Number: <b>{COMPANY_INFO['rc_number']}</b>, having its principal office at",
                normal_style
            ))
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            
            # 1.2 The Officer
            story.append(Paragraph(
                f"<b>1.2 The Officer:</b> {user_data.get('full_name', 'CORE MARSHAL')}, "
                "with National Identification Number: ",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>{user_data.get('nin_number', '{Number}')}</b>, ",
                bold_style
            ))
            story.append(Paragraph(
                "residing at",
                normal_style
            ))
            story.append(Paragraph(
                f"{user_data.get('residential_address', 'Address not provided')}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # Build PDF
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Terms & Conditions", is_terms=True)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Terms & Conditions PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Terms & Conditions PDF: {str(e)}")
    
    def generate_application_form(self, user_data: Dict[str, Any], user_id: str) -> str:
        """Generate Application Form PDF with passport photo"""
        try:
            logger.info(f"Generating Application Form PDF for user: {user_id}")
            
            filename = self._generate_filename(user_id, "application")
            filepath, relative_path = self._save_pdf("applications", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,
                bottomMargin=72
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'TitleStyle',
                parent=styles['Title'],
                fontSize=16,
                textColor=colors.HexColor('#1a237e'),
                alignment=TA_CENTER,
                spaceAfter=12,
                fontName='Helvetica-Bold'
            )
            
            heading1_style = ParagraphStyle(
                'Heading1',
                parent=styles['Heading1'],
                fontSize=12,
                textColor=colors.HexColor('#283593'),
                spaceBefore=12,
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                fontName='Helvetica'
            )
            
            bold_style = ParagraphStyle(
                'BoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1a237e')
            )
            
            # ✅ PASSPORT PHOTO SECTION - FIXED AND WORKING
            passport_embedded = False
            passport_table = None
            
            passport_path = user_data.get('passport_photo') or user_data.get('passport_path')
            if passport_path:
                passport_img = self._prepare_passport_image(passport_path)
                if passport_img:
                    # Create table for passport photo
                    passport_data = [
                        [Paragraph("<b>PASSPORT PHOTO</b>", bold_style)],
                        [passport_img]
                    ]
                    
                    passport_table = Table(passport_data, colWidths=[2*inch])
                    passport_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('PADDING', (0, 0), (-1, -1), 6),
                    ]))
                    passport_embedded = True
                    logger.info("✅ Passport photo embedded in PDF")
            
            # Start content
            # Title
            story.append(Paragraph("MARSHAL CORE OF NIGERIA", title_style))
            story.append(Paragraph("OFFICER APPLICATION FORM", title_style))
            story.append(Spacer(1, 12))
            
            # Organization Information
            story.append(Paragraph(
                f"<b>Organization:</b> Marshal Core of Nigeria (Voluntary Organization)",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Certificate Number:</b> {COMPANY_INFO['certificate_number']}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>RC Number:</b> {COMPANY_INFO['rc_number']}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Address:</b> {COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # Application Information
            story.append(Paragraph(
                f"<b>Application ID:</b> {user_data.get('unique_id', user_id)}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Submission Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # Two-column layout for Personal Info and Passport Photo
            if passport_table and passport_embedded:
                # Create two-column table
                personal_info_data = []
                
                # Personal Information Section
                personal_info_data.append([Paragraph("PERSONAL INFORMATION", heading1_style), ""])
                
                # Full Name
                personal_info_data.append([
                    Paragraph(f"<b>Full Name:</b> {user_data.get('full_name', 'N/A')}", normal_style),
                    ""])
                
                # Officer ID
                personal_info_data.append([
                    Paragraph(f"<b>Officer ID:</b> {user_data.get('unique_id', user_data.get('officer_id', 'N/A'))}", normal_style),
                    ""])
                
                # NIN Number
                personal_info_data.append([
                    Paragraph(f"<b>NIN Number:</b> {user_data.get('nin_number', 'N/A')}", normal_style),
                    ""])
                
                # Other personal info
                personal_fields = [
                    ("Date of Birth", self._format_date(user_data.get('date_of_birth'))),
                    ("Gender", user_data.get('gender', 'N/A')),
                    ("Marital Status", user_data.get('marital_status', 'N/A')),
                    ("Nationality", user_data.get('nationality', 'N/A')),
                    ("Religion", user_data.get('religion', 'N/A')),
                    ("Place of Birth", user_data.get('place_of_birth', 'N/A')),
                ]
                
                for label, value in personal_fields:
                    personal_info_data.append([
                        Paragraph(f"<b>{label}:</b> {value}", normal_style),
                        ""])
                
                # Create table with 2 columns
                two_col_table = Table([
                    [Table(personal_info_data, colWidths=[4*inch, 2*inch]), passport_table]
                ], colWidths=[4*inch, 2.5*inch])
                
                two_col_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                
                story.append(two_col_table)
                story.append(Spacer(1, 12))
            else:
                # Single column layout (no passport)
                story.append(Paragraph("PERSONAL INFORMATION", heading1_style))
                story.append(Paragraph(
                    f"<b>Full Name:</b> {user_data.get('full_name', 'N/A')}", normal_style))
                story.append(Paragraph(
                    f"<b>Officer ID:</b> {user_data.get('unique_id', user_data.get('officer_id', 'N/A'))}", normal_style))
                story.append(Paragraph(
                    f"<b>NIN Number:</b> {user_data.get('nin_number', 'N/A')}", normal_style))
                story.append(Spacer(1, 12))
            
            # Contact Information
            story.append(Paragraph("CONTACT INFORMATION", heading1_style))
            
            contact_fields = [
                ("Email Address", user_data.get('email', 'N/A')),
                ("Phone Number", user_data.get('phone', user_data.get('mobile_number', 'N/A'))),
                ("Residential Address", user_data.get('residential_address', 'N/A')),
                ("State of Residence", user_data.get('state_of_residence', 'N/A')),
                ("LGA of Residence", user_data.get('local_government_residence', user_data.get('lga', 'N/A'))),
                ("Country of Residence", user_data.get('country_of_residence', 'N/A')),
            ]
            
            for label, value in contact_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Origin Information
            story.append(Paragraph("ORIGIN INFORMATION", heading1_style))
            
            origin_fields = [
                ("State of Origin", user_data.get('state_of_origin', 'N/A')),
                ("LGA of Origin", user_data.get('local_government_origin', 'N/A')),
            ]
            
            for label, value in origin_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Professional Information
            story.append(Paragraph("PROFESSIONAL INFORMATION", heading1_style))
            
            professional_fields = [
                ("Rank", user_data.get('rank', 'CORE MARSHAL')),
                ("Position", user_data.get('position', 'Officer')),
                ("Additional Skills", user_data.get('additional_skills', 'N/A')),
            ]
            
            for label, value in professional_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Financial Information
            story.append(Paragraph("FINANCIAL INFORMATION", heading1_style))
            
            financial_fields = [
                ("Bank Name", user_data.get('bank_name', 'N/A')),
                ("Account Number", user_data.get('account_number', 'N/A')),
            ]
            
            for label, value in financial_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 12))
            
            # Documents Submitted
            story.append(Paragraph("DOCUMENTS SUBMITTED", heading1_style))
            
            documents = [
                ("Passport Photo", "✓ Submitted" if passport_embedded else "✗ Not Submitted"),
                ("NIN Slip", "✓ Submitted" if user_data.get('nin_number') else "✗ Not Submitted"),
            ]
            
            for label, value in documents:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 2))
            
            story.append(Spacer(1, 24))
            
            # Declaration
            story.append(Paragraph("DECLARATION", heading1_style))
            story.append(Paragraph(
                "I hereby declare that all information provided in this application is true and correct "
                "to the best of my knowledge. I understand that any false information may lead to "
                "disqualification or termination of appointment as per the Terms and Conditions.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Signature lines
            story.append(Paragraph("<b>Signature of Officer:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}", bold_style))
            story.append(Spacer(1, 48))
            
            # Organization signature
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            story.append(Spacer(1, 12))
            
            # Footer note
            story.append(Paragraph(
                "This document is electronically generated by Marshal Core of Nigeria. "
                "For official use only.",
                ParagraphStyle(
                    'FooterNote',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_CENTER
                )
            ))
            
            # Build PDF
            def on_first_page(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
            
            def on_later_pages(canvas_obj, doc_obj):
                self._create_header_footer(canvas_obj, doc_obj, "Application Form")
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Application Form PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Application Form PDF: {str(e)}")
    
    def generate_both_pdfs(self, user_data: Dict[str, Any], user_id: str) -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        """
        try:
            logger.info(f"Generating both PDFs for user: {user_id}")
            
            # Generate Terms & Conditions
            terms_pdf_path = self.generate_terms_conditions(user_data, user_id)
            
            # Generate Application Form
            app_pdf_path = self.generate_application_form(user_data, user_id)
            
            return {
                "terms_pdf_path": terms_pdf_path,
                "application_pdf_path": app_pdf_path,
                "generated_at": datetime.now().isoformat(),
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"Failed to generate both PDFs: {str(e)}")
            raise PDFGenerationError(f"Failed to generate both PDFs: {str(e)}")

# Singleton instance
pdf_generator = PDFGenerator()


class PDFService:
    """Service class for PDF operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_user_data(self, user_id: str, user_type: str) -> Dict[str, Any]:
        """Get user data for PDF generation"""
        user_data = {}
        
        if user_type == "applicant":
            user = self.db.query(Applicant).filter(Applicant.id == user_id).first()
            if user:
                user_data = {
                    'unique_id': user.unique_id,
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'nin_number': user.nin_number,
                    'date_of_birth': user.date_of_birth,
                    'state_of_residence': user.state_of_residence,
                    'lga': user.lga,
                    'address': user.address,
                    'passport_photo': user.passport_photo,
                    'nin_slip': user.nin_slip,
                    'application_tier': user.application_tier,
                    'selected_reasons': user.selected_reasons,
                    'additional_details': user.additional_details,
                    'gender': getattr(user, 'gender', 'N/A'),
                    'marital_status': getattr(user, 'marital_status', 'N/A'),
                    'nationality': getattr(user, 'nationality', 'N/A'),
                    'religion': getattr(user, 'religion', 'N/A'),
                    'place_of_birth': getattr(user, 'place_of_birth', 'N/A'),
                    'bank_name': getattr(user, 'bank_name', 'N/A'),
                    'account_number': getattr(user, 'account_number', 'N/A'),
                    'additional_skills': getattr(user, 'additional_skills', 'N/A'),
                }
        
        elif user_type == "officer":
            user = self.db.query(Officer).filter(Officer.id == user_id).first()
            if user:
                user_data = {
                    'unique_id': user.unique_id,
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone': user.phone,
                    'nin_number': user.nin_number,
                    'date_of_birth': user.date_of_birth,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'passport_photo': user.passport,
                    'rank': user.rank,
                    'position': user.position,
                    'additional_skills': user.additional_skills,
                    'nationality': user.nationality,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'religion': user.religion,
                    'place_of_birth': user.place_of_birth,
                    'marital_status': user.marital_status,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'category': user.category,
                    'gender': user.gender,
                }
        
        elif user_type == "existing_officer":
            user = self.db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
            if user:
                user_data = {
                    'officer_id': user.officer_id,
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone': user.phone,
                    'nin_number': user.nin_number,
                    'date_of_birth': user.date_of_birth,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'passport_photo': user.passport_path,
                    'rank': user.rank,
                    'position': user.position,
                    'additional_skills': user.additional_skills,
                    'nationality': user.nationality,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'religion': user.religion,
                    'place_of_birth': user.place_of_birth,
                    'marital_status': user.marital_status,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'category': user.category,
                    'gender': user.gender,
                    'date_of_enlistment': user.date_of_enlistment,
                    'date_of_promotion': user.date_of_promotion,
                    'years_of_service': user.years_of_service,
                    'service_number': user.service_number,
                }
        
        return user_data
    
    def generate_both_pdfs(self, user_id: str, user_type: str) -> Dict[str, str]:
        """
        Generate both PDFs for a user
        """
        try:
            user_data = self._get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            return pdf_generator.generate_both_pdfs(user_data, user_id)
            
        except Exception as e:
            logger.error(f"Failed to generate PDFs for {user_id}: {str(e)}")
            raise
    
    def generate_terms_conditions(self, user_id: str, user_type: str) -> str:
        """Generate Terms & Conditions PDF"""
        try:
            user_data = self._get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            return pdf_generator.generate_terms_conditions(user_data, user_id)
            
        except Exception as e:
            logger.error(f"Failed to generate Terms PDF for {user_id}: {str(e)}")
            raise
    
    def generate_application_form(self, user_id: str, user_type: str) -> str:
        """Generate Application Form PDF with passport photo"""
        try:
            user_data = self._get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            return pdf_generator.generate_application_form(user_data, user_id)
            
        except Exception as e:
            logger.error(f"Failed to generate Application PDF for {user_id}: {str(e)}")
            raise
    
    def get_existing_pdfs(self, user_id: str, user_type: str) -> Dict[str, Any]:
        """Get existing PDF paths from database"""
        result = {
            "terms_pdf_path": None,
            "application_pdf_path": None,
            "terms_generated_at": None,
            "application_generated_at": None,
        }
        
        try:
            if user_type == "applicant":
                user = self.db.query(Applicant).filter(Applicant.id == user_id).first()
                if user:
                    result["terms_pdf_path"] = user.terms_pdf_path
                    result["application_pdf_path"] = user.application_pdf_path
                    result["terms_generated_at"] = user.terms_generated_at
                    result["application_generated_at"] = user.application_generated_at
            
            elif user_type == "officer":
                user = self.db.query(Officer).filter(Officer.id == user_id).first()
                if user:
                    result["terms_pdf_path"] = user.terms_pdf_path
                    result["application_pdf_path"] = user.application_pdf_path
                    result["terms_generated_at"] = user.terms_generated_at
                    result["application_generated_at"] = user.application_generated_at
            
            elif user_type == "existing_officer":
                user = self.db.query(ExistingOfficer).filter(ExistingOfficer.id == user_id).first()
                if user:
                    result["terms_pdf_path"] = user.terms_pdf_path
                    result["application_pdf_path"] = user.registration_pdf_path
                    result["terms_generated_at"] = user.terms_generated_at
                    result["application_generated_at"] = user.registration_generated_at
        
        except Exception as e:
            logger.error(f"Error getting PDF paths: {str(e)}")
        
        return result