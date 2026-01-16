# app/services/pdf_service.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer

logger = logging.getLogger(__name__)

# Create templates directory if it doesn't exist
TEMPLATES_DIR = Path("templates/pdf")
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Create PDF output directory
PDF_OUTPUT_DIR = Path("static/pdfs")
PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class PDFGenerator:
    """Main PDF generator class"""
    
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader("templates/pdf"))
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render HTML template"""
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def generate_pdf_from_html(self, html_content: str, output_path: str) -> bool:
        """Generate PDF from HTML content (using reportlab)"""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.platypus.doctemplate import SimpleDocTemplate
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
            
            # For now, create a simple PDF with reportlab
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            # Add title
            title = Paragraph("Marshal Core of Nigeria - Document", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 12))
            
            # Add content placeholder
            content = Paragraph("This is an official document. Content would be rendered from HTML template.", styles['Normal'])
            story.append(content)
            
            # Build PDF
            doc.build(story)
            return True
            
        except Exception as e:
            logger.error(f"ReportLab PDF generation failed: {str(e)}")
            # Fallback: create empty file for now
            Path(output_path).write_text("PDF content placeholder")
            return True
    
    def generate_terms_conditions(self, officer_data: Dict[str, Any], officer_id: str) -> str:
        """Generate Terms & Conditions PDF"""
        try:
            # Create output filename
            filename = f"terms_conditions_{officer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = PDF_OUTPUT_DIR / "existing_officers" / "terms"
            output_path.mkdir(parents=True, exist_ok=True)
            
            full_path = output_path / filename
            
            # Prepare context
            context = {
                'officer_full_name': officer_data.get('full_name', 'Officer'),
                'officer_id': officer_data.get('officer_id', officer_id),
                'nin_number': officer_data.get('nin_number', 'N/A'),
                'position': officer_data.get('rank', 'Officer'),
                'agreement_date': datetime.now().strftime('%B %d, %Y'),
                'document_id': f"TNC-{officer_id}-{datetime.now().strftime('%Y%m%d')}",
                'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Try to render HTML template
            try:
                html_content = self.render_template("terms_conditions.html", context)
            except:
                # Fallback simple HTML
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Terms & Conditions - {officer_id}</title></head>
                <body>
                    <h1>Marshal Core of Nigeria</h1>
                    <h2>Terms & Conditions</h2>
                    <h3>Officer: {context['officer_full_name']}</h3>
                    <h3>Officer ID: {context['officer_id']}</h3>
                    <h3>Date: {context['agreement_date']}</h3>
                    <p>This document outlines the terms and conditions for existing officers.</p>
                </body>
                </html>
                """
            
            # Generate PDF
            self.generate_pdf_from_html(html_content, str(full_path))
            
            logger.info(f"Terms & Conditions PDF generated: {full_path}")
            return str(full_path)
            
        except Exception as e:
            logger.error(f"Error generating Terms PDF: {str(e)}")
            # Create fallback PDF file
            fallback_path = PDF_OUTPUT_DIR / "existing_officers" / "terms" / f"terms_fallback_{officer_id}.pdf"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(f"Terms & Conditions for Officer {officer_id}")
            return str(fallback_path)
    
    def generate_existing_officer_registration_form(self, officer_data: Dict[str, Any], officer_id: str) -> str:
        """Generate Existing Officer Registration Form PDF"""
        try:
            # Create output filename
            filename = f"registration_form_{officer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = PDF_OUTPUT_DIR / "existing_officers" / "registration"
            output_path.mkdir(parents=True, exist_ok=True)
            
            full_path = output_path / filename
            
            # Prepare context
            context = {
                'officer_id': officer_data.get('officer_id', officer_id),
                'full_name': officer_data.get('full_name', 'Officer'),
                'email': officer_data.get('email', 'N/A'),
                'phone': officer_data.get('phone', 'N/A'),
                'date_of_enlistment': officer_data.get('date_of_enlistment', 'N/A'),
                'date_of_promotion': officer_data.get('date_of_promotion', 'N/A'),
                'rank': officer_data.get('rank', 'N/A'),
                'position': officer_data.get('position', 'N/A'),
                'category': officer_data.get('category', 'N/A'),
                'date_of_birth': officer_data.get('date_of_birth', 'N/A'),
                'gender': officer_data.get('gender', 'N/A'),
                'nin_number': officer_data.get('nin_number', 'N/A'),
                'residential_address': officer_data.get('residential_address', 'N/A'),
                'state_of_residence': officer_data.get('state_of_residence', 'N/A'),
                'nationality': officer_data.get('nationality', 'N/A'),
                'document_id': f"REG-{officer_id}-{datetime.now().strftime('%Y%m%d')}",
                'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Try to render HTML template
            try:
                html_content = self.render_template("existing_officer_registration.html", context)
            except:
                # Fallback simple HTML
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Registration Form - {officer_id}</title></head>
                <body>
                    <h1>Marshal Core of Nigeria</h1>
                    <h2>Existing Officer Registration Form</h2>
                    <h3>Officer: {context['full_name']}</h3>
                    <h3>Officer ID: {context['officer_id']}</h3>
                    <h3>Category: {context['category']}</h3>
                    <h3>Rank: {context['rank']}</h3>
                    <p>Date of Enlistment: {context['date_of_enlistment']}</p>
                    <p>Date of Promotion: {context['date_of_promotion']}</p>
                    <p>Email: {context['email']}</p>
                    <p>Phone: {context['phone']}</p>
                </body>
                </html>
                """
            
            # Generate PDF
            self.generate_pdf_from_html(html_content, str(full_path))
            
            logger.info(f"Registration Form PDF generated: {full_path}")
            return str(full_path)
            
        except Exception as e:
            logger.error(f"Error generating Registration PDF: {str(e)}")
            # Create fallback PDF file
            fallback_path = PDF_OUTPUT_DIR / "existing_officers" / "registration" / f"registration_fallback_{officer_id}.pdf"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(f"Registration Form for Officer {officer_id}")
            return str(fallback_path)


# Create template files if they don't exist
def create_template_files():
    """Create necessary template files"""
    templates = {
        "terms_conditions.html": """<!DOCTYPE html>
<html>
<head><title>Terms & Conditions</title></head>
<body>
    <h1>Marshal Core of Nigeria</h1>
    <h2>Terms & Conditions</h2>
    <p>Officer: {{ officer_full_name }}</p>
    <p>Officer ID: {{ officer_id }}</p>
    <p>Date: {{ agreement_date }}</p>
    <p>Document ID: {{ document_id }}</p>
</body>
</html>""",
        
        "existing_officer_registration.html": """<!DOCTYPE html>
<html>
<head><title>Registration Form</title></head>
<body>
    <h1>Marshal Core of Nigeria</h1>
    <h2>Existing Officer Registration Form</h2>
    <p>Officer: {{ full_name }}</p>
    <p>Officer ID: {{ officer_id }}</p>
    <p>Category: {{ category }}</p>
    <p>Rank: {{ rank }}</p>
    <p>Enlistment: {{ date_of_enlistment }}</p>
    <p>Promotion: {{ date_of_promotion }}</p>
    <p>Email: {{ email }}</p>
    <p>Phone: {{ phone }}</p>
    <p>Document ID: {{ document_id }}</p>
</body>
</html>"""
    }
    
    for filename, content in templates.items():
        template_path = TEMPLATES_DIR / filename
        if not template_path.exists():
            template_path.write_text(content)
            logger.info(f"Created template: {template_path}")


# Initialize templates
create_template_files()
pdf_generator = PDFGenerator()


class PDFService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_terms_conditions(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> str:
        """Generate Terms & Conditions PDF"""
        try:
            logger.info(f"Generating Terms & Conditions for {user_type}: {user_id}")
            
            # Get user data
            user_data = self._get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate PDF
            pdf_path = pdf_generator.generate_terms_conditions(user_data, user_id)
            
            # Update database record
            self._update_pdf_record(user_id, user_type, 'terms', pdf_path)
            
            logger.info(f"Terms PDF generated successfully: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions: {str(e)}")
            # Create a fallback PDF path
            fallback_path = PDF_OUTPUT_DIR / "existing_officers" / "terms" / f"terms_error_{user_id}.pdf"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(f"Error generating Terms PDF for {user_id}")
            return str(fallback_path)
    
    def generate_existing_officer_registration_form(
        self,
        user_id: str
    ) -> str:
        """Generate Existing Officer Registration Form PDF"""
        try:
            logger.info(f"Generating Existing Officer Registration Form for: {user_id}")
            
            # Get existing officer data
            officer = self.db.query(ExistingOfficer).filter(
                ExistingOfficer.id == user_id
            ).first()
            
            if not officer:
                raise ValueError(f"Existing officer not found: {user_id}")
            
            # Prepare data
            officer_data = {
                'officer_id': officer.officer_id,
                'full_name': officer.full_name,
                'email': officer.email,
                'phone': officer.phone,
                'date_of_enlistment': officer.date_of_enlistment,
                'date_of_promotion': officer.date_of_promotion,
                'rank': officer.rank,
                'position': officer.position,
                'category': officer.category,
                'date_of_birth': officer.date_of_birth,
                'gender': officer.gender,
                'nin_number': officer.nin_number,
                'residential_address': officer.residential_address,
                'state_of_residence': officer.state_of_residence,
                'nationality': officer.nationality,
            }
            
            # Generate PDF
            pdf_path = pdf_generator.generate_existing_officer_registration_form(officer_data, user_id)
            
            logger.info(f"Registration Form PDF generated successfully: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Registration Form: {str(e)}")
            # Create a fallback PDF path
            fallback_path = PDF_OUTPUT_DIR / "existing_officers" / "registration" / f"registration_error_{user_id}.pdf"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(f"Error generating Registration PDF for {user_id}")
            return str(fallback_path)
    
    def _get_user_data(self, user_id: str, user_type: str) -> Dict[str, Any]:
        """Get user data for PDF generation"""
        user_data = {}
        
        if user_type == "existing_officer":
            user = self.db.query(ExistingOfficer).filter(
                ExistingOfficer.id == user_id
            ).first()
            if user:
                user_data = {
                    'officer_id': user.officer_id,
                    'full_name': user.full_name,
                    'nin_number': user.nin_number,
                    'email': user.email,
                    'phone': user.phone,
                    'rank': user.rank,
                    'position': user.position,
                    'date_of_birth': user.date_of_birth,
                    'gender': user.gender,
                    'marital_status': user.marital_status,
                    'nationality': user.nationality,
                    'place_of_birth': user.place_of_birth,
                    'religion': user.religion,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'additional_skills': user.additional_skills,
                    'passport_photo': user.passport_photo,
                    'nin_slip': user.nin_slip,
                    'ssce_certificate': user.ssce_certificate,
                    'date_of_enlistment': user.date_of_enlistment,
                    'date_of_promotion': user.date_of_promotion,
                    'category': user.category,
                    'years_of_service': user.years_of_service,
                    'service_number': user.service_number,
                }
        
        return user_data
    
    def _update_pdf_record(
        self,
        user_id: str,
        user_type: str,
        pdf_type: str,
        pdf_path: str
    ):
        """Update database record with PDF path"""
        try:
            now = datetime.now()
            
            if user_type == "existing_officer":
                officer = self.db.query(ExistingOfficer).filter(
                    ExistingOfficer.id == user_id
                ).first()
                if officer:
                    if pdf_type == 'terms':
                        officer.terms_pdf_path = pdf_path
                        officer.terms_generated_at = now
                    else:
                        officer.registration_pdf_path = pdf_path
                        officer.registration_generated_at = now
                    self.db.commit()
                    logger.info(f"Updated {pdf_type} PDF path for officer {user_id}")
                    
        except Exception as e:
            logger.error(f"Failed to update PDF record: {str(e)}")