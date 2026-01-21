# app/utils/pdf.py
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid
import requests
from io import BytesIO

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
PDFS_DIR = STATIC_DIR / "pdfs"
TERMS_DIR = PDFS_DIR / "terms"
APPLICATIONS_DIR = PDFS_DIR / "applications"
LOGO_DIR = STATIC_DIR / "images"

# Ensure directories exist
for directory in [PDFS_DIR, TERMS_DIR, APPLICATIONS_DIR, LOGO_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Company information - Updated with correct details
COMPANY_INFO = {
    "name": "Marshal Core of Nigeria",  # Changed from "Marshal Core Nigeria"
    "certificate_number": "YA/CLB/10100",
    "rc_number": "8405988",
    "address_line1": "KM. 3, MARSHAL CORE OF NIGERIA NATIONAL HEADQUARTERS",
    "address_line2": "ABUMWENRENRE COMMUNITY, EKIADOLOR/AGEKPANU ROAD",
    "address_line3": "BENIN CITY, EDO STATE, NIGERIA",
    "phone": "+234 9137 428 031",
    "email": "info@marshalcoreofnigeria.ng",
    "website": "www.marshalcoreofnigeria.ng",
    "logo_url": "https://marshalcoreofnigeria.ng/images/logo.png"
}

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

# Keep this function exactly as it was
async def generate_existing_officer_pdfs_and_email(officer_id: str, email: str, full_name: str, db: Session):
    """
    ✅ Generate PDFs and send email with DIRECT DOWNLOAD LINKS
    This function is called by the route handler
    """
    from app.models.existing_officer import ExistingOfficer
    from app.services.email_service import send_existing_officer_pdfs_email
    from app.services.existing_officer_service import ExistingOfficerService
    
    try:
        logger.info(f"🔄 Starting PDF auto-generation for existing officer: {officer_id}")
        
        # Get officer
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            logger.error(f"❌ Officer not found: {officer_id}")
            return {"success": False, "error": "Officer not found"}
        
        logger.info(f"✅ Found officer: {full_name} ({email})")
        
        # Generate PDFs using the PDFGenerator class
        pdf_gen = PDFGenerator()
        
        # Prepare officer data for PDF generation
        officer_data = {
            "full_name": full_name,
            "nin_number": officer.nin_number,
            "residential_address": officer.residential_address,
            "rank": officer.rank,
            "position": officer.position,
            "unique_id": officer_id,
            "email": email,
            "phone": officer.phone,
            "gender": officer.gender,
            "marital_status": officer.marital_status,
            "nationality": officer.nationality,
            "religion": officer.religion,
            "place_of_birth": officer.place_of_birth,
            "date_of_birth": officer.date_of_birth,
            "state_of_residence": officer.state_of_residence,
            "local_government_residence": officer.local_government_residence,
            "country_of_residence": officer.country_of_residence,
            "state_of_origin": officer.state_of_origin,
            "local_government_origin": officer.local_government_origin,
            "years_of_service": officer.years_of_service,
            "service_number": officer.service_number,
            "additional_skills": officer.additional_skills,
            "bank_name": officer.bank_name,
            "account_number": officer.account_number,
            "date_of_enlistment": officer.date_of_enlistment,
            "date_of_promotion": officer.date_of_promotion,
            "category": officer.category,
            "passport_photo": officer.passport_path,  # Using new field
        }
        
        logger.info(f"📄 Generating Terms & Conditions PDF for {officer_id}")
        terms_pdf_path = pdf_gen.generate_terms_conditions(officer_data, str(officer.id))
        
        logger.info(f"📄 Generating Application Form PDF for {officer_id}")
        app_pdf_path = pdf_gen.generate_application_form(officer_data, str(officer.id))
        
        # ✅ CREATE PUBLIC DOWNLOAD URLs
        base_url = "https://backend-mcn-ltd.onrender.com"
        terms_filename = os.path.basename(terms_pdf_path)
        registration_filename = os.path.basename(app_pdf_path)
        
        terms_pdf_url = f"{base_url}/download/pdf/{terms_filename}"
        registration_pdf_url = f"{base_url}/download/pdf/{registration_filename}"
        
        logger.info(f"✅ Generated download URLs:")
        logger.info(f"   Terms: {terms_pdf_url}")
        logger.info(f"   Registration: {registration_pdf_url}")
        
        # Update PDF paths in database
        ExistingOfficerService.update_pdf_paths(
            db,
            officer_id,
            terms_pdf_path,
            app_pdf_path  # This should be registration_pdf_path
        )
        
        # ✅ Send email with DIRECT DOWNLOAD LINKS
        email_result = await send_existing_officer_pdfs_email(
            to_email=email,
            name=full_name,
            officer_id=officer_id,
            terms_pdf_path=terms_pdf_path,
            registration_pdf_path=app_pdf_path
        )
        
        if email_result:
            logger.info(f"📧 Email with download links queued for {email}")
        else:
            logger.warning(f"⚠️ Email queuing failed for {email}")
        
        logger.info(f"✅ PDF generation and email queuing COMPLETE for {officer_id}")
        
        return {
            "success": True,
            "officer_id": officer_id,
            "email": email,
            "terms_pdf_path": terms_pdf_path,
            "registration_pdf_path": app_pdf_path,
            "terms_pdf_url": terms_pdf_url,
            "registration_pdf_url": registration_pdf_url,
            "email_queued": email_result
        }
            
    except Exception as e:
        logger.error(f"❌ Error generating PDFs for {officer_id}: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

class PDFGenerator:
    """PDF generation utility using ReportLab"""
    
    def __init__(self):
        """Initialize PDF generator"""
        logger.info("Initializing ReportLab PDF Generator")
        self.logo_image = None
        self._try_load_logo()
    
    def _try_load_logo(self):
        """Try to load logo from URL or local file"""
        try:
            # Try to download logo from URL
            response = requests.get(COMPANY_INFO['logo_url'], timeout=10)
            if response.status_code == 200:
                self.logo_image = BytesIO(response.content)
                logger.info("✅ Logo loaded successfully from URL")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not load logo from URL: {e}")
        
        # Try local file
        logo_path = LOGO_DIR / "logo.png"
        if logo_path.exists():
            try:
                with open(logo_path, 'rb') as f:
                    self.logo_image = BytesIO(f.read())
                logger.info("✅ Logo loaded from local file")
                return True
            except Exception as e:
                logger.warning(f"⚠️ Could not load local logo: {e}")
        
        logger.warning("❌ Could not load logo, will use text placeholder")
        return False
    
    def _generate_filename(self, user_id: str, document_type: str) -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, category: str, filename: str) -> str:
        """Get filepath for saving PDF"""
        category_dir = PDFS_DIR / category
        category_dir.mkdir(exist_ok=True)
        
        file_path = category_dir / filename
        
        # Return relative path for web access
        relative_path = f"static/pdfs/{category}/{filename}"
        logger.info(f"PDF will be saved to: {relative_path}")
        return str(file_path), relative_path
    
    def _create_header_footer(self, canvas, doc, title="", is_terms=False):
        """Create header and footer for all pages with logo"""
        canvas.saveState()
        
        # Add logo at top right corner if available
        if self.logo_image:
            try:
                # Draw logo at top right
                logo_width = 1.2 * inch
                logo_height = 0.6 * inch
                logo_x = doc.width + inch - logo_width - 0.2*inch
                logo_y = doc.height + inch - 0.1*inch
                
                canvas.drawImage(self.logo_image, logo_x, logo_y, 
                               width=logo_width, height=logo_height, 
                               mask='auto', preserveAspectRatio=True)
            except Exception as e:
                logger.warning(f"Could not draw logo image: {e}")
                # Fallback to text
                self._draw_logo_placeholder(canvas, doc)
        else:
            # Draw text placeholder for logo
            self._draw_logo_placeholder(canvas, doc)
        
        # Header text
        canvas.setFont('Helvetica-Bold', 12)
        canvas.setFillColor(colors.HexColor('#1a237e'))
        canvas.drawString(inch, doc.height + inch + 0.6*inch, COMPANY_INFO['name'])
        
        # Address in 3 lines
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        
        address_y = doc.height + inch + 0.4*inch
        canvas.drawString(inch, address_y, COMPANY_INFO['address_line1'])
        canvas.drawString(inch, address_y - 0.15*inch, COMPANY_INFO['address_line2'])
        canvas.drawString(inch, address_y - 0.3*inch, COMPANY_INFO['address_line3'])
        
        # Draw line under header
        canvas.setStrokeColor(colors.HexColor('#1a237e'))
        canvas.setLineWidth(1)
        canvas.line(inch, doc.height + inch + 0.1*inch, doc.width + inch, doc.height + inch + 0.1*inch)
        
        # Footer
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        
        # Left footer - page number
        canvas.drawString(inch, 0.5*inch, f"Page {doc.page}")
        
        # Center footer - document info
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas.drawCentredString(doc.width/2 + inch, 0.5*inch, doc_info)
        
        # Right footer - date
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawRightString(doc.width + inch, 0.5*inch, date_str)
        
        # Draw line above footer
        canvas.setStrokeColor(colors.lightgrey)
        canvas.setLineWidth(0.5)
        canvas.line(inch, 0.7*inch, doc.width + inch, 0.7*inch)
        
        canvas.restoreState()
    
    def _draw_logo_placeholder(self, canvas, doc):
        """Draw logo placeholder text"""
        canvas.setFillColor(colors.HexColor('#1a237e'))
        canvas.setFont('Helvetica-Bold', 12)
        canvas.drawRightString(doc.width + inch - 0.2*inch, doc.height + inch + 0.4*inch, "MCN")
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(doc.width + inch - 0.2*inch, doc.height + inch + 0.2*inch, "LOGO")
    
    def _add_background_watermark(self, canvas, doc):
        """Add logo as background watermark"""
        canvas.saveState()
        
        # Only add watermark if logo is available
        if self.logo_image:
            try:
                # Set transparency
                canvas.setFillAlpha(0.08)  # 8% opacity
                
                # Calculate position for centered watermark
                center_x = doc.width/2 + inch
                center_y = doc.height/2 + inch
                
                # Draw logo watermark
                logo_width = 3 * inch
                logo_height = 1.5 * inch
                logo_x = center_x - logo_width/2
                logo_y = center_y - logo_height/2
                
                canvas.drawImage(self.logo_image, logo_x, logo_y, 
                               width=logo_width, height=logo_height, 
                               mask='auto', preserveAspectRatio=True)
            except Exception as e:
                logger.warning(f"Could not draw watermark: {e}")
                # Fallback to text watermark
                self._draw_text_watermark(canvas, doc)
        else:
            # Draw text watermark
            self._draw_text_watermark(canvas, doc)
        
        canvas.restoreState()
    
    def _draw_text_watermark(self, canvas, doc):
        """Draw text watermark"""
        canvas.setFillAlpha(0.1)  # 10% opacity
        
        # Calculate position for centered watermark
        center_x = doc.width/2 + inch
        center_y = doc.height/2 + inch
        
        # Rotate the watermark
        canvas.translate(center_x, center_y)
        canvas.rotate(45)
        
        # Draw MCN text as watermark
        canvas.setFont('Helvetica-Bold', 48)
        canvas.setFillColor(colors.lightgrey)
        canvas.drawCentredString(0, 0, "MCN")
        
        canvas.setFont('Helvetica', 24)
        canvas.drawCentredString(0, -40, "Marshal Core of Nigeria")
    
    def generate_terms_conditions(self, officer_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Terms & Conditions PDF for an officer
        
        Args:
            officer_data: Dictionary containing officer information
            user_id: Unique identifier for the user
        
        Returns:
            Relative path to generated PDF file
        """
        try:
            logger.info(f"Generating Terms & Conditions PDF for user: {user_id}")
            
            # Generate filename
            filename = self._generate_filename(user_id, "terms")
            filepath, relative_path = self._save_pdf("terms", filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,  # Extra space for header and logo
                bottomMargin=72
            )
            
            # Story (content) container
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
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
                leftIndent=0,
                fontName='Helvetica-Bold'
            )
            
            heading2_style = ParagraphStyle(
                'Heading2',
                parent=styles['Heading2'],
                fontSize=12,
                textColor=colors.HexColor('#3949ab'),
                spaceBefore=10,
                spaceAfter=4,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalJustified',
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
            
            warning_style = ParagraphStyle(
                'WarningStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.red,
                fontSize=10
            )
            
            nin_bold_style = ParagraphStyle(
                'NINBoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.black
            )
            
            # Title
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            # Document Information
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-NG-{user_id}-{datetime.now().strftime('%Y%m%d')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Effective Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # IMPORTANT NOTICE - Updated with exact text from document
            story.append(Paragraph(
                "<b>IMPORTANT NOTICE:</b> This is a legally binding agreement between "
                "Marshal Core of Nigeria (hereinafter referred to as 'the Organization') "  # Changed
                "and the Officer/Applicant (hereinafter referred to as 'the Officer'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            # 1. PARTIES TO THE AGREEMENT - Updated with exact text
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            
            # 1.1 The Organization - Updated with exact text
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
            
            # 1.2 The Officer - Updated to use officer's actual name from data
            story.append(Paragraph(
                f"<b>1.2 The Officer:</b> {officer_data.get('full_name', 'CORE MARSHAL')}, "
                "with National Identification Number: ",
                normal_style
            ))
            # NIN in bold
            story.append(Paragraph(
                f"<b>{officer_data.get('nin_number', '{Number}')}</b>, ",
                nin_bold_style
            ))
            story.append(Paragraph(
                "residing at",
                normal_style
            ))
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 2. APPOINTMENT AND DUTIES - Updated with exact text
            story.append(Paragraph("2. APPOINTMENT AND DUTIES", heading1_style))
            
            # 2.1 Appointment - Updated with exact text
            story.append(Paragraph(
                "<b>2.1 Appointment:</b> The Officer is hereby appointed as Director in the "
                "None department, subject to the terms and conditions herein.",
                normal_style
            ))
            
            # 2.2 Duties - Updated with exact text
            story.append(Paragraph(
                "<b>2.2 Duties:</b> The Officer shall perform all duties assigned by the organization "
                "including but not limited to security services, patrol duties, client protection, "
                "and any other lawful instructions from authorized supervisors.",
                normal_style
            ))
            
            # 2.3 Code of Conduct - Updated with exact text
            story.append(Paragraph(
                "<b>2.3 Code of Conduct:</b> The Officer shall at all times maintain the highest "
                "standards of professionalism, integrity, and discipline as outlined in the "
                "organization Code of Conduct Manual.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            # 3. TERM AND TERMINATION - Updated with exact text
            story.append(Paragraph("3. TERM AND TERMINATION", heading1_style))
            
            # 3.1 Term - Updated with exact text
            story.append(Paragraph(
                '<b>3.1 Term:</b> This agreement shall commence on "Date" and continue until '
                "terminated in accordance with these terms.",
                normal_style
            ))
            
            # 3.2 Termination for Cause - Updated with exact text
            story.append(Paragraph(
                "<b>3.2 Termination for Cause:</b> The organization may immediately terminate this agreement for:",
                normal_style
            ))
            
            # Updated termination reasons to match document exactly
            termination_reasons = [
                "Criminal conduct or conviction",
                "Gross misconduct or negligence",
                "Violation of organization policies",
                "Unauthorized disclosure of confidential information",
                "Failure to perform assigned duties",
                "Absence without leave for more than 2 consecutive months"
            ]
            
            for reason in termination_reasons:
                story.append(Paragraph(f"• {reason}", normal_style))
            
            story.append(Spacer(1, 6))
            
            # 4. LEGAL CONSEQUENCES OF MISCONDUCT - Updated with exact text
            story.append(Paragraph("4. LEGAL CONSEQUENCES OF MISCONDUCT", heading1_style))
            
            # Page header from document
            story.append(Paragraph(
                f'Page 1 Terms & Conditions "{datetime.now().strftime("%d/%m/%Y %H:%M")}"',
                ParagraphStyle(
                    'PageHeader',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.gray,
                    alignment=TA_RIGHT
                )
            ))
            
            story.append(Paragraph(
                "Marshal Core of Nigeria",  # Changed from COMPANY_INFO['name']
                ParagraphStyle(
                    'CompanyHeader',
                    parent=normal_style,
                    fontSize=9,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold'
                )
            ))
            
            story.append(Paragraph(
                f"{COMPANY_INFO['address_line1']}<br/>{COMPANY_INFO['address_line2']}<br/>{COMPANY_INFO['address_line3']}",
                ParagraphStyle(
                    'AddressHeader',
                    parent=normal_style,
                    fontSize=8,
                    alignment=TA_CENTER
                )
            ))
            
            story.append(Spacer(1, 6))
            
            # WARNING section - Updated with exact text from document
            story.append(Paragraph("WARNING:", warning_style))
            story.append(Paragraph(
                "Any breach of these terms may result in:",
                normal_style
            ))
            
            # Updated legal consequences to match document exactly
            legal_consequences = [
                "Immediate termination of employment/voluntary service",
                "Forfeiture of all benefits and entitlements",
                "Returning/seizure of all marshal property in your possession including the marshal property you bought by yourself. Read this most carefully",
                "Legal prosecution in accordance with Nigerian laws",
                "Civil liability for damages caused",
                "Criminal charges where applicable",
                "Court proceedings and possible imprisonment",
                "Financial penalties and compensation payments"
            ]
            
            for consequence in legal_consequences:
                if "including the marshal property you bought by yourself" in consequence:
                    story.append(Paragraph(f"• {consequence}", warning_style))
                else:
                    story.append(Paragraph(f"• {consequence}", normal_style))
            
            story.append(Spacer(1, 12))
            
            # 5. CONFIDENTIALITY - Updated with exact text
            story.append(Paragraph("5. CONFIDENTIALITY", heading1_style))
            
            # 5.1 Confidential Information - Updated with exact text
            story.append(Paragraph(
                "<b>5.1 Confidential Information:</b> The Officer shall not disclose any confidential "
                "information about the Organization, its clients, or operations during or after employment.",
                normal_style
            ))
            
            # 5.2 Non-Disclosure - Updated with exact text (10 years)
            story.append(Paragraph(
                "<b>5.2 Non-Disclosure:</b> This obligation continues for 10 years after termination of employment.",
                normal_style
            ))
            
            story.append(Spacer(1, 12))
            
            # Page break for signature section
            story.append(PageBreak())
            
            # ACCEPTANCE AND SIGNATURE SECTION - Updated with exact text
            story.append(Paragraph("ACCEPTANCE AND SIGNATURE", heading1_style))
            story.append(Spacer(1, 24))
            
            # Using officer's actual name from data
            story.append(Paragraph(
                f'I, "{officer_data.get("full_name", "Name")}" hereby acknowledge that I have read, '
                "understood, and agree to be bound by all the terms and conditions stated in this document.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            # Officer Signature
            story.append(Paragraph("<b>Signature of Officer:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 48))
            
            # Organization Signature - Updated with exact text from document
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            story.append(Spacer(1, 12))
            
            # Build PDF with custom canvas
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas, doc)
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
                self._add_background_watermark(canvas, doc)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Terms & Conditions PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Terms & Conditions PDF: {str(e)}")
    
    def generate_application_form(self, applicant_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Application Form PDF for an applicant/officer
        
        Args:
            applicant_data: Dictionary containing applicant information
            user_id: Unique identifier for the user
        
        Returns:
            Relative path to generated PDF file
        """
        try:
            logger.info(f"Generating Application Form PDF for user: {user_id}")
            
            # Generate filename
            filename = self._generate_filename(user_id, "application")
            filepath, relative_path = self._save_pdf("applications", filename)
            
            # Create PDF document
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,  # Extra space for header and logo
                bottomMargin=72
            )
            
            # Story (content) container
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
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
                leftIndent=0,
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'NormalStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                fontName='Helvetica'
            )
            
            field_label_style = ParagraphStyle(
                'FieldLabel',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1a237e')
            )
            
            nin_bold_style = ParagraphStyle(
                'NINBoldStyle',
                parent=normal_style,
                fontName='Helvetica-Bold',
                textColor=colors.black
            )
            
            # Title - Changed from "Limited" to match document
            story.append(Paragraph("MARSHAL CORE OF NIGERIA", title_style))  # Changed
            story.append(Paragraph("OFFICER APPLICATION FORM", title_style))
            story.append(Spacer(1, 12))
            
            # Organization Information from the document
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
                f"<b>Application ID:</b> {applicant_data.get('unique_id', user_id)}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Submission Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # Personal Information Section
            story.append(Paragraph("PERSONAL INFORMATION", heading1_style))
            
            # Full Name
            story.append(Paragraph(f"<b>Full Name:</b> {applicant_data.get('full_name', 'N/A')}", normal_style))
            story.append(Spacer(1, 4))
            
            # Officer ID
            story.append(Paragraph(f"<b>Officer ID:</b> {applicant_data.get('unique_id', applicant_data.get('officer_id', 'N/A'))}", normal_style))
            story.append(Spacer(1, 4))
            
            # NIN Number in BOLD
            story.append(Paragraph("<b>NIN Number:</b> ", normal_style))
            story.append(Paragraph(f"<b>{applicant_data.get('nin_number', 'N/A')}</b>", nin_bold_style))
            story.append(Spacer(1, 4))
            
            # Other personal info
            personal_info_fields = [
                ("Date of Birth", self._format_date(applicant_data.get('date_of_birth'))),
                ("Gender", applicant_data.get('gender', 'N/A')),
                ("Marital Status", applicant_data.get('marital_status', 'N/A')),
                ("Nationality", applicant_data.get('nationality', 'N/A')),
                ("Religion", applicant_data.get('religion', 'N/A')),
                ("Place of Birth", applicant_data.get('place_of_birth', 'N/A')),
            ]
            
            for label, value in personal_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Contact Information
            story.append(Paragraph("CONTACT INFORMATION", heading1_style))
            
            contact_info_fields = [
                ("Email Address", applicant_data.get('email', 'N/A')),
                ("Phone Number", applicant_data.get('phone', applicant_data.get('mobile_number', 'N/A'))),
                ("Residential Address", f"{COMPANY_INFO['address_line1']}, {COMPANY_INFO['address_line2']}, {COMPANY_INFO['address_line3']}"),
                ("State of Residence", applicant_data.get('state_of_residence', 'N/A')),
                ("LGA of Residence", applicant_data.get('local_government_residence', 'N/A')),
                ("Country of Residence", applicant_data.get('country_of_residence', 'N/A')),
            ]
            
            for label, value in contact_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Origin Information
            story.append(Paragraph("ORIGIN INFORMATION", heading1_style))
            
            origin_info_fields = [
                ("State of Origin", applicant_data.get('state_of_origin', 'N/A')),
                ("LGA of Origin", applicant_data.get('local_government_origin', 'N/A')),
            ]
            
            for label, value in origin_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Professional Information
            story.append(Paragraph("PROFESSIONAL INFORMATION", heading1_style))
            
            # Updated to match document format - using "Director in None department"
            professional_info_fields = [
                ("Rank", applicant_data.get('rank', 'CORE MARSHAL')),
                ("Position", "Director in None department"),
                ("Years of Service", applicant_data.get('years_of_service', 'N/A')),
                ("Service Number", applicant_data.get('service_number', 'N/A')),
                ("Additional Skills", applicant_data.get('additional_skills', 'N/A')),
            ]
            
            for label, value in professional_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Financial Information
            story.append(Paragraph("FINANCIAL INFORMATION", heading1_style))
            
            financial_info_fields = [
                ("Bank Name", applicant_data.get('bank_name', 'N/A')),
                ("Account Number", applicant_data.get('account_number', 'N/A')),
            ]
            
            for label, value in financial_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Service Dates
            story.append(Paragraph("SERVICE DATES", heading1_style))
            
            service_date_fields = [
                ("Date of Enlistment", self._format_date(applicant_data.get('date_of_enlistment'))),
                ("Date of Promotion", self._format_date(applicant_data.get('date_of_promotion'))),
            ]
            
            for label, value in service_date_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            # Documents Submitted
            story.append(Paragraph("DOCUMENTS SUBMITTED", heading1_style))
            
            documents_info_fields = [
                ("Passport Photo", "✓ Submitted" if applicant_data.get('passport_photo') else "✗ Not Submitted"),
                ("NIN Slip", "✓ Submitted" if applicant_data.get('nin_number') else "✗ Not Submitted"),
            ]
            
            for label, value in documents_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
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
            
            # Signature lines - Updated to match document format
            story.append(Paragraph("<b>Signature of Officer:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}", field_label_style))
            story.append(Spacer(1, 48))
            
            # Organization signature - Updated to match document
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", field_label_style))
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
            
            # Build PDF with custom canvas
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
                self._add_background_watermark(canvas, doc)
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
                self._add_background_watermark(canvas, doc)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Application Form PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Application Form PDF: {str(e)}")
    
    def _format_date(self, date_value):
        """Format date for display"""
        if not date_value:
            return "N/A"
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime("%d %B, %Y")
        
        if isinstance(date_value, str):
            try:
                # Try to parse various date formats
                from datetime import datetime as dt
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"]:
                    try:
                        parsed_date = dt.strptime(date_value, fmt)
                        return parsed_date.strftime("%d %B, %Y")
                    except:
                        continue
            except:
                pass
        
        return str(date_value)
    
    def generate_both_pdfs(self, user_data: Dict[str, Any], user_id: str) -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        
        Args:
            user_data: Dictionary containing user information
            user_id: Unique identifier for the user
        
        Returns:
            Dictionary with paths to both PDFs
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

# Singleton instance for easy import
pdf_generator = PDFGenerator()