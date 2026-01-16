# app/services/pdf_service.py
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.utils.pdf import pdf_generator
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.models.existing_officer import ExistingOfficer
# Remove the problematic import and create the class locally

logger = logging.getLogger(__name__)

class ExistingOfficerPDFGenerator:
    """PDF Generator for Existing Officers - LOCAL VERSION"""
    def __init__(self):
        pass
    
    def generate_registration_form(self, officer_data: Dict[str, Any]) -> str:
        """Generate Existing Officer Registration Form PDF"""
        try:
            import os
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from datetime import datetime as dt
            
            # Create filename
            officer_id = officer_data.get('officer_id', 'unknown').replace('/', '_')
            filename = f"existing_officer_{officer_id}_registration_{dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            
            # Create directory
            base_dir = os.path.join("static", "pdfs", "existing_officers")
            os.makedirs(base_dir, exist_ok=True)
            filepath = os.path.join(base_dir, filename)
            
            # Create PDF
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            story = []
            
            # Create header
            styles = getSampleStyleSheet()
            
            # Add title
            story.append(Paragraph("EXISTING OFFICER REGISTRATION FORM", styles['Title']))
            story.append(Spacer(1, 20))
            
            # Officer information
            info_data = [
                ["Officer ID:", officer_data.get('officer_id', 'N/A')],
                ["Full Name:", officer_data.get('full_name', 'N/A')],
                ["Email:", officer_data.get('email', 'N/A')],
                ["Phone:", officer_data.get('phone', 'N/A')],
                ["Date of Enlistment:", str(officer_data.get('date_of_enlistment', 'N/A'))],
                ["Date of Promotion:", str(officer_data.get('date_of_promotion', 'N/A'))],
                ["Rank:", officer_data.get('rank', 'N/A')],
                ["Position:", officer_data.get('position', 'N/A')],
                ["Category:", officer_data.get('category', 'N/A')],
            ]
            
            table = Table(info_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
            
            # Add footer
            story.append(Paragraph(f"Generated on: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"Existing Officer PDF generated: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating existing officer PDF: {str(e)}")
            raise Exception(f"Failed to generate PDF: {str(e)}")


class PDFService:
    def __init__(self, db: Session):
        self.db = db
        self.existing_officer_generator = ExistingOfficerPDFGenerator()  # Use local class
    
    def get_user_data(self, user_id: str, user_type: str) -> Dict[str, Any]:
        """Get user data for PDF generation based on user type"""
        user_data = {}
        
        if user_type == "applicant":
            user = self.db.query(Applicant).filter(Applicant.id == user_id).first()
            if user:
                user_data = {
                    'id': str(user.id),
                    'unique_id': user.unique_id,
                    'full_name': user.full_name,
                    'nin_number': user.nin_number,
                    'email': user.email,
                    'mobile_number': user.mobile_number,
                    'phone_number': user.phone_number,
                    'gender': user.gender,
                    'date_of_birth': user.date_of_birth,
                    'marital_status': user.marital_status,
                    'nationality': user.nationality,
                    'place_of_birth': user.place_of_birth,
                    'religion': user.religion,
                    'category': user.category,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'local_government_residence': user.local_government_residence,
                    'country_of_residence': user.country_of_residence,
                    'state_of_origin': user.state_of_origin,
                    'local_government_origin': user.local_government_origin,
                    'bank_name': user.bank_name,
                    'account_number': user.account_number,
                    'passport_photo': user.passport_photo,
                    'nin_slip': user.nin_slip,
                    'ssce_certificate': user.ssce_certificate,
                    'higher_education_degree': user.higher_education_degree,
                    'do_you_smoke': user.do_you_smoke,
                    'agree_to_join': user.agree_to_join,
                    'agree_to_abide_rules': user.agree_to_abide_rules,
                    'agree_to_return_properties': user.agree_to_return_properties,
                    'additional_skills': user.additional_skills,
                    'design_rating': user.design_rating,
                }
        
        elif user_type == "officer":
            user = self.db.query(Officer).filter(Officer.id == user_id).first()
            if user:
                user_data = {
                    'id': str(user.id),
                    'unique_id': user.unique_id,
                    'full_name': user.full_name or "Officer",
                    'email': user.email,
                    'phone': user.phone,
                    'rank': user.rank,
                    'position': user.position,
                    'date_of_birth': user.date_of_birth,
                    'gender': user.gender,
                    'nin_number': user.nin_number,
                    'residential_address': user.residential_address,
                    'state_of_residence': user.state_of_residence,
                    'additional_skills': user.additional_skills,
                }
                
                # Try to get more data from applicant if available
                if user.applicant:
                    applicant = user.applicant
                    user_data.update({
                        'full_name': applicant.full_name or user_data['full_name'],
                        'nin_number': applicant.nin_number or user_data['nin_number'],
                        'date_of_birth': applicant.date_of_birth or user_data['date_of_birth'],
                        'gender': applicant.gender or user_data['gender'],
                        'marital_status': applicant.marital_status,
                        'nationality': applicant.nationality,
                        'place_of_birth': applicant.place_of_birth,
                        'religion': applicant.religion,
                        'category': applicant.category,
                        'residential_address': applicant.residential_address or user_data['residential_address'],
                        'state_of_residence': applicant.state_of_residence or user_data['state_of_residence'],
                        'local_government_residence': applicant.local_government_residence,
                        'country_of_residence': applicant.country_of_residence,
                        'state_of_origin': applicant.state_of_origin,
                        'local_government_origin': applicant.local_government_origin,
                        'bank_name': applicant.bank_name,
                        'account_number': applicant.account_number,
                        'passport_photo': applicant.passport_photo,
                        'nin_slip': applicant.nin_slip,
                        'ssce_certificate': applicant.ssce_certificate,
                        'higher_education_degree': applicant.higher_education_degree,
                        'do_you_smoke': applicant.do_you_smoke,
                        'agree_to_join': applicant.agree_to_join,
                        'agree_to_abide_rules': applicant.agree_to_abide_rules,
                        'agree_to_return_properties': applicant.agree_to_return_properties,
                        'additional_skills': applicant.additional_skills or user_data['additional_skills'],
                        'design_rating': applicant.design_rating,
                    })
        
        elif user_type == "existing_officer":
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
                    # NEW FIELDS FOR EXISTING OFFICERS
                    'date_of_enlistment': user.date_of_enlistment,
                    'date_of_promotion': user.date_of_promotion,
                    'category': user.category,
                    'years_of_service': user.years_of_service,
                    'service_number': user.service_number,
                }
        
        return user_data
    
    def generate_terms_conditions(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> str:
        """
        Generate Terms & Conditions PDF for a user
        """
        try:
            logger.info(f"Generating Terms & Conditions for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate PDF
            pdf_path = pdf_generator.generate_terms_conditions(user_data, user_id)
            
            # Update database record
            self._update_pdf_record(user_id, user_type, 'terms', pdf_path)
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Terms & Conditions: {str(e)}")
            raise
    
    def generate_application_form(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> str:
        """
        Generate Application Form PDF for a user
        """
        try:
            logger.info(f"Generating Application Form for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate PDF
            if user_type == "existing_officer":
                # Use new template for existing officers
                pdf_path = self.generate_existing_officer_registration_form(user_id)
            else:
                # Use regular application form for others
                pdf_path = pdf_generator.generate_application_form(user_data, user_id)
            
            # Update database record
            self._update_pdf_record(user_id, user_type, 'application', pdf_path)
            
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Application Form: {str(e)}")
            raise
    
    def generate_existing_officer_registration_form(
        self,
        user_id: str
    ) -> str:
        """
        Generate Existing Officer Registration Form PDF - NEW METHOD
        
        Creates a specific PDF template for existing officers
        """
        try:
            logger.info(f"Generating Existing Officer Registration Form for: {user_id}")
            
            # Get existing officer data
            officer = self.db.query(ExistingOfficer).filter(
                ExistingOfficer.id == user_id
            ).first()
            
            if not officer:
                raise ValueError(f"Existing officer not found: {user_id}")
            
            # Prepare data for PDF generation
            pdf_data = {
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
            
            # Generate PDF using the local generator
            pdf_path = self.existing_officer_generator.generate_registration_form(pdf_data)
            
            logger.info(f"Existing Officer Registration Form generated: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            logger.error(f"Failed to generate Existing Officer Registration Form: {str(e)}")
            raise
    
    def generate_both_pdfs(
        self,
        user_id: str,
        user_type: str = "applicant"
    ) -> Dict[str, str]:
        """
        Generate both Terms & Conditions and Application Form PDFs
        """
        try:
            logger.info(f"Generating both PDFs for {user_type}: {user_id}")
            
            # Get user data
            user_data = self.get_user_data(user_id, user_type)
            if not user_data:
                raise ValueError(f"User not found: {user_id}")
            
            # Generate both PDFs
            terms_pdf_path = self.generate_terms_conditions(user_id, user_type)
            
            if user_type == "existing_officer":
                application_pdf_path = self.generate_existing_officer_registration_form(user_id)
            else:
                application_pdf_path = self.generate_application_form(user_id, user_type)
            
            pdf_paths = {
                'terms_pdf_path': terms_pdf_path,
                'application_pdf_path': application_pdf_path
            }
            
            # Update database records
            self._update_pdf_record(
                user_id, 
                user_type, 
                'terms', 
                pdf_paths['terms_pdf_path']
            )
            self._update_pdf_record(
                user_id, 
                user_type, 
                'application', 
                pdf_paths['application_pdf_path']
            )
            
            return pdf_paths
            
        except Exception as e:
            logger.error(f"Failed to generate both PDFs: {str(e)}")
            raise
    
    def _update_pdf_record(
        self,
        user_id: str,
        user_type: str,
        pdf_type: str,
        pdf_path: str
    ):
        """
        Update database record with PDF path
        """
        try:
            now = datetime.now()
            
            if user_type == "applicant":
                applicant = self.db.query(Applicant).filter(Applicant.id == user_id).first()
                if applicant:
                    if pdf_type == 'terms':
                        applicant.terms_pdf_path = pdf_path
                        applicant.terms_generated_at = now
                    else:
                        applicant.application_pdf_path = pdf_path
                        applicant.application_generated_at = now
                    self.db.commit()
            
            elif user_type == "officer":
                officer = self.db.query(Officer).filter(Officer.id == user_id).first()
                if officer:
                    if pdf_type == 'terms':
                        officer.terms_pdf_path = pdf_path
                        officer.terms_generated_at = now
                    else:
                        officer.application_pdf_path = pdf_path
                        officer.application_generated_at = now
                    self.db.commit()
            
            elif user_type == "existing_officer":
                officer = self.db.query(ExistingOfficer).filter(
                    ExistingOfficer.id == user_id
                ).first()
                if officer:
                    if pdf_type == 'terms':
                        officer.terms_pdf_path = pdf_path
                        officer.terms_generated_at = now
                    else:
                        officer.registration_pdf_path = pdf_path  # Changed from application_pdf_path
                        officer.registration_generated_at = now
                    self.db.commit()
                    
        except Exception as e:
            logger.error(f"Failed to update PDF record: {str(e)}")
    
    def get_existing_officer_pdf_status(
        self,
        officer_id: str
    ) -> Dict[str, Any]:
        """
        Check PDF generation status for existing officer
        """
        try:
            officer = self.db.query(ExistingOfficer).filter(
                ExistingOfficer.officer_id == officer_id
            ).first()
            
            if not officer:
                return {
                    "has_terms": False,
                    "has_registration": False,
                    "terms_generated_at": None,
                    "registration_generated_at": None,
                    "message": "Officer not found"
                }
            
            return {
                "has_terms": bool(officer.terms_pdf_path),
                "has_registration": bool(officer.registration_pdf_path),
                "terms_generated_at": officer.terms_generated_at,
                "registration_generated_at": officer.registration_generated_at,
                "terms_path": officer.terms_pdf_path,
                "registration_path": officer.registration_pdf_path,
                "message": "PDF status retrieved successfully"
            }
            
        except Exception as e:
            logger.error(f"Error getting PDF status: {str(e)}")
            return {
                "has_terms": False,
                "has_registration": False,
                "message": f"Error: {str(e)}"
            }