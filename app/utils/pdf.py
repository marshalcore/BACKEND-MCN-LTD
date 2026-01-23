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
import base64

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
PDFS_DIR = STATIC_DIR / "pdfs"
TERMS_DIR = PDFS_DIR / "terms"
APPLICATIONS_DIR = PDFS_DIR / "applications"
LOGO_DIR = STATIC_DIR / "images"

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
    "logo_url": "https://marshalcoreofnigeria.ng/images/logo.png"
}

class PDFGenerationError(Exception):
    """Custom exception for PDF generation errors"""
    pass

async def generate_existing_officer_pdfs_and_email(officer_id: str, email: str, full_name: str, db: Session):
    """
    Generate PDFs and send email with DIRECT DOWNLOAD LINKS
    """
    from app.models.existing_officer import ExistingOfficer
    from app.services.email_service import send_existing_officer_pdfs_email
    from app.services.existing_officer_service import ExistingOfficerService
    
    try:
        logger.info(f"🔄 Starting PDF auto-generation for existing officer: {officer_id}")
        
        # Get officer with all details
        officer = db.query(ExistingOfficer).filter(
            ExistingOfficer.officer_id == officer_id
        ).first()
        
        if not officer:
            logger.error(f"❌ Officer not found: {officer_id}")
            return {"success": False, "error": "Officer not found"}
        
        logger.info(f"✅ Found officer: {full_name} ({email})")
        
        # Generate PDFs using the PDFGenerator class
        pdf_gen = PDFGenerator()
        
        # Get passport photo path correctly
        passport_photo_path = None
        if officer.passport_path:
            passport_full_path = os.path.join(UPLOADS_DIR, officer.passport_path)
            if os.path.exists(passport_full_path):
                passport_photo_path = passport_full_path
                logger.info(f"✅ Passport photo found: {passport_photo_path}")
            else:
                logger.warning(f"⚠️ Passport photo not found at: {passport_full_path}")
        
        # Prepare officer data for PDF generation
        officer_data = {
            "full_name": officer.full_name,
            "nin_number": officer.nin_number,
            "residential_address": officer.residential_address,
            "rank": officer.rank,
            "position": officer.position,
            "unique_id": officer.officer_id,
            "email": officer.email,
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
            "passport_photo_path": passport_photo_path,
        }
        
        logger.info(f"📄 Generating Terms & Conditions PDF for {officer_id}")
        terms_pdf_path = pdf_gen.generate_terms_conditions(officer_data, str(officer.id))
        
        logger.info(f"📄 Generating Application Form PDF for {officer_id}")
        app_pdf_path = pdf_gen.generate_application_form(officer_data, str(officer.id))
        
        # Create download URLs
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
            app_pdf_path
        )
        
        # Send email
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
        self.logo_data = None
        self._load_logo()
    
    def _load_logo(self):
        """Load logo from local file"""
        try:
            # Try local file first
            logo_path = LOGO_DIR / "logo.png"
            if logo_path.exists():
                with open(logo_path, 'rb') as f:
                    self.logo_data = BytesIO(f.read())
                logger.info("✅ Logo loaded successfully from local file")
                return True
            
            # Try backup local file
            backup_logo_path = BASE_DIR / "logo.png"
            if backup_logo_path.exists():
                with open(backup_logo_path, 'rb') as f:
                    self.logo_data = BytesIO(f.read())
                logger.info("✅ Logo loaded from backup location")
                return True
            
            logger.warning("❌ Could not find logo file")
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Could not load logo: {e}")
            return False
    
    def _generate_filename(self, user_id: str, document_type: str) -> str:
        """Generate unique filename for PDF"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}_{document_type}_{timestamp}_{unique_id}.pdf"
    
    def _save_pdf(self, category: str, filename: str) -> str:
        """Get filepath for saving PDF"""
        category_dir = PDFS_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = category_dir / filename
        
        relative_path = f"static/pdfs/{category}/{filename}"
        logger.info(f"PDF will be saved to: {relative_path}")
        return str(file_path), relative_path
    
    def _load_passport_photo(self, photo_path: str):
        """Load and resize passport photo"""
        if not photo_path or not os.path.exists(photo_path):
            return None
        
        try:
            img = PILImage.open(photo_path)
            
            # Calculate size for PDF
            max_width = 1.5 * 150
            max_height = 1.5 * 150
            
            width_ratio = max_width / img.width
            height_ratio = max_height / img.height
            ratio = min(width_ratio, height_ratio)
            
            new_width = int(img.width * ratio)
            new_height = int(img.height * ratio)
            
            img = img.resize((new_width, new_height), PILImage.Resampling.LANCZOS)
            
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            return {
                'data': img_bytes,
                'width': new_width / 150,
                'height': new_height / 150
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Could not load passport photo: {e}")
            return None
    
    def _create_header_footer(self, canvas, doc, title="", is_terms=False):
        """Create header and footer for all pages with logo"""
        canvas.saveState()
        
        # Add logo at top left corner
        if self.logo_data:
            try:
                logo_width = 1.5 * inch
                logo_height = 0.8 * inch
                logo_x = inch
                logo_y = doc.height + inch - 0.2*inch
                
                canvas.drawImage(self.logo_data, logo_x, logo_y, 
                               width=logo_width, height=logo_height, 
                               mask='auto', preserveAspectRatio=True)
                
                # Draw company name beside logo
                canvas.setFont('Helvetica-Bold', 16)
                canvas.setFillColor(colors.HexColor('#1a237e'))
                canvas.drawString(logo_x + logo_width + 0.2*inch, 
                                 logo_y + logo_height/2 - 0.1*inch, 
                                 COMPANY_INFO['name'])
                
            except Exception as e:
                logger.warning(f"Could not draw logo image: {e}")
                self._draw_logo_placeholder(canvas, doc)
        else:
            self._draw_logo_placeholder(canvas, doc)
        
        # Footer
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.gray)
        
        canvas.drawString(inch, 0.5*inch, f"Page {doc.page}")
        
        doc_info = "Terms & Conditions" if is_terms else "Application Form"
        canvas.drawCentredString(doc.width/2 + inch, 0.5*inch, doc_info)
        
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawRightString(doc.width + inch, 0.5*inch, date_str)
        
        canvas.setStrokeColor(colors.lightgrey)
        canvas.setLineWidth(0.5)
        canvas.line(inch, 0.7*inch, doc.width + inch, 0.7*inch)
        
        canvas.restoreState()
    
    def _draw_logo_placeholder(self, canvas, doc):
        """Draw logo placeholder text"""
        canvas.setFillColor(colors.HexColor('#1a237e'))
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawString(inch, doc.height + inch + 0.5*inch, COMPANY_INFO['name'])
    
    def generate_terms_conditions(self, officer_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Terms & Conditions PDF for an officer
        """
        try:
            logger.info(f"Generating Terms & Conditions PDF for user: {user_id}")
            
            filename = self._generate_filename(user_id, "terms")
            filepath, relative_path = self._save_pdf("terms", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=100,
                bottomMargin=72
            )
            
            story = []
            
            styles = getSampleStyleSheet()
            
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
            
            story.append(Paragraph("TERMS AND CONDITIONS OF SERVICE", title_style))
            story.append(Spacer(1, 12))
            
            story.append(Paragraph(
                f"<b>Document Reference:</b> MCN-NG-{user_id}-{datetime.now().strftime('%Y%m%d')}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Effective Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph(
                "<b>IMPORTANT NOTICE:</b> This is a legally binding agreement between "
                "Marshal Core of Nigeria (hereinafter referred to as 'the Organization') "
                "and the Officer/Applicant (hereinafter referred to as 'the Officer'). "
                "Please read carefully before accepting.",
                bold_style
            ))
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("1. PARTIES TO THE AGREEMENT", heading1_style))
            
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
            
            # Use officer's ACTUAL residential address
            story.append(Paragraph(
                f"<b>1.2 The Officer:</b> {officer_data.get('full_name', 'CORE MARSHAL')}, "
                "with National Identification Number: ",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>{officer_data.get('nin_number', '{Number}')}</b>, ",
                normal_style
            ))
            story.append(Paragraph(
                "residing at",
                normal_style
            ))
            officer_address = officer_data.get('residential_address', 'Address not provided')
            story.append(Paragraph(
                f"{officer_address}",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("2. APPOINTMENT AND DUTIES", heading1_style))
            story.append(Paragraph(
                "<b>2.1 Appointment:</b> The Officer is hereby appointed as Director in the "
                "None department, subject to the terms and conditions herein.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>2.2 Duties:</b> The Officer shall perform all duties assigned by the organization "
                "including but not limited to security services, patrol duties, client protection, "
                "and any other lawful instructions from authorized supervisors.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>2.3 Code of Conduct:</b> The Officer shall at all times maintain the highest "
                "standards of professionalism, integrity, and discipline as outlined in the "
                "organization Code of Conduct Manual.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("3. TERM AND TERMINATION", heading1_style))
            story.append(Paragraph(
                '<b>3.1 Term:</b> This agreement shall commence on "Date" and continue until '
                "terminated in accordance with these terms.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>3.2 Termination for Cause:</b> The organization may immediately terminate this agreement for:",
                normal_style
            ))
            
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
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("4. LEGAL CONSEQUENCES OF MISCONDUCT", heading1_style))
            story.append(Paragraph("WARNING:", bold_style))
            story.append(Paragraph(
                "Any breach of these terms may result in:",
                normal_style
            ))
            
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
                    story.append(Paragraph(f"• {consequence}", bold_style))
                else:
                    story.append(Paragraph(f"• {consequence}", normal_style))
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("5. CONFIDENTIALITY", heading1_style))
            story.append(Paragraph(
                "<b>5.1 Confidential Information:</b> The Officer shall not disclose any confidential "
                "information about the Organization, its clients, or operations during or after employment.",
                normal_style
            ))
            story.append(Paragraph(
                "<b>5.2 Non-Disclosure:</b> This obligation continues for 10 years after termination of employment.",
                normal_style
            ))
            story.append(Spacer(1, 12))
            
            story.append(PageBreak())
            
            story.append(Paragraph("ACCEPTANCE AND SIGNATURE", heading1_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph(
                f'I, "{officer_data.get("full_name", "Name")}" hereby acknowledge that I have read, '
                "understood, and agree to be bound by all the terms and conditions stated in this document.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            story.append(Paragraph("<b>Signature of Officer:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 48))
            
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", bold_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", bold_style))
            story.append(Spacer(1, 12))
            
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Terms & Conditions", is_terms=True)
            
            doc.build(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
            
            logger.info(f"Terms & Conditions PDF generated successfully: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions PDF: {str(e)}")
            raise PDFGenerationError(f"Failed to generate Terms & Conditions PDF: {str(e)}")
    
    def generate_application_form(self, applicant_data: Dict[str, Any], user_id: str) -> str:
        """
        Generate Application Form PDF for an applicant/officer with passport photo
        """
        try:
            logger.info(f"Generating Application Form PDF for user: {user_id}")
            
            filename = self._generate_filename(user_id, "application")
            filepath, relative_path = self._save_pdf("applications", filename)
            
            doc = SimpleDocTemplate(
                filepath,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=100,
                bottomMargin=72
            )
            
            story = []
            
            styles = getSampleStyleSheet()
            
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
            
            story.append(Paragraph("MARSHAL CORE OF NIGERIA", title_style))
            story.append(Paragraph("OFFICER APPLICATION FORM", title_style))
            story.append(Spacer(1, 12))
            
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
            
            story.append(Paragraph(
                f"<b>Application ID:</b> {applicant_data.get('unique_id', user_id)}",
                normal_style
            ))
            story.append(Paragraph(
                f"<b>Submission Date:</b> {datetime.now().strftime('%d %B %Y')}",
                normal_style
            ))
            story.append(Spacer(1, 24))
            
            # Table with passport photo
            table_data = []
            
            passport_cell_content = []
            passport_photo = self._load_passport_photo(applicant_data.get('passport_photo_path'))
            
            if passport_photo:
                passport_cell_content.append(Image(passport_photo['data'], 
                                                  width=passport_photo['width']*inch, 
                                                  height=passport_photo['height']*inch))
                passport_cell_content.append(Paragraph("<b>Passport Photo</b>", normal_style))
            
            table_data.append([
                Paragraph(f"<b>Full Name:</b><br/>{applicant_data.get('full_name', 'N/A')}", normal_style),
                passport_cell_content if passport_cell_content else Paragraph("Passport Photo<br/>(Not Submitted)", normal_style)
            ])
            
            table = Table(table_data, colWidths=[3.5*inch, 2*inch])
            table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 12))
            
            story.append(Paragraph(f"<b>Officer ID:</b> {applicant_data.get('unique_id', applicant_data.get('officer_id', 'N/A'))}", normal_style))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>NIN Number:</b> {applicant_data.get('nin_number', 'N/A')}", normal_style))
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("PERSONAL INFORMATION", heading1_style))
            
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
            
            story.append(Paragraph("CONTACT INFORMATION", heading1_style))
            
            contact_info_fields = [
                ("Email Address", applicant_data.get('email', 'N/A')),
                ("Phone Number", applicant_data.get('phone', applicant_data.get('mobile_number', 'N/A'))),
                ("Residential Address", applicant_data.get('residential_address', 'Address not provided')),
                ("State of Residence", applicant_data.get('state_of_residence', 'N/A')),
                ("LGA of Residence", applicant_data.get('local_government_residence', 'N/A')),
                ("Country of Residence", applicant_data.get('country_of_residence', 'N/A')),
            ]
            
            for label, value in contact_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("ORIGIN INFORMATION", heading1_style))
            
            origin_info_fields = [
                ("State of Origin", applicant_data.get('state_of_origin', 'N/A')),
                ("LGA of Origin", applicant_data.get('local_government_origin', 'N/A')),
            ]
            
            for label, value in origin_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("PROFESSIONAL INFORMATION", heading1_style))
            
            professional_info_fields = [
                ("Rank", applicant_data.get('rank', 'CORE MARSHAL')),
                ("Position", applicant_data.get('position', 'N/A')),
                ("Years of Service", applicant_data.get('years_of_service', 'N/A')),
                ("Service Number", applicant_data.get('service_number', 'N/A')),
                ("Additional Skills", applicant_data.get('additional_skills', 'N/A')),
            ]
            
            for label, value in professional_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("FINANCIAL INFORMATION", heading1_style))
            
            financial_info_fields = [
                ("Bank Name", applicant_data.get('bank_name', 'N/A')),
                ("Account Number", applicant_data.get('account_number', 'N/A')),
            ]
            
            for label, value in financial_info_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 12))
            
            story.append(Paragraph("SERVICE DATES", heading1_style))
            
            service_date_fields = [
                ("Date of Enlistment", self._format_date(applicant_data.get('date_of_enlistment'))),
                ("Date of Promotion", self._format_date(applicant_data.get('date_of_promotion'))),
            ]
            
            for label, value in service_date_fields:
                story.append(Paragraph(f"<b>{label}:</b> {value}", normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("DECLARATION", heading1_style))
            story.append(Paragraph(
                "I hereby declare that all information provided in this application is true and correct "
                "to the best of my knowledge. I understand that any false information may lead to "
                "disqualification or termination of appointment as per the Terms and Conditions.",
                normal_style
            ))
            story.append(Spacer(1, 48))
            
            story.append(Paragraph("<b>Signature of Officer:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Spacer(1, 24))
            story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}", field_label_style))
            story.append(Spacer(1, 48))
            
            story.append(Paragraph("<b>For Marshal Core of Nigeria:</b>", field_label_style))
            story.append(Spacer(1, 48))
            story.append(Paragraph("________________________________________", normal_style))
            story.append(Paragraph("Name: OSEOBOH JOSHUA EROMONSELE", normal_style))
            story.append(Paragraph("RANK: Director General", normal_style))
            story.append(Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y')}", normal_style))
            story.append(Spacer(1, 24))
            
            story.append(Paragraph("<b>Official Stamp:</b>", field_label_style))
            story.append(Spacer(1, 12))
            
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
            
            def on_first_page(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
            
            def on_later_pages(canvas, doc):
                self._create_header_footer(canvas, doc, "Application Form")
            
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

pdf_generator = PDFGenerator()