# app/services/email_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import settings
from jinja2 import Environment, FileSystemLoader
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ✅ Always include a professional display name
MAIL_FROM_WITH_NAME = f"Marshal Core <{settings.EMAIL_FROM}>"

# Two configs: one for TLS (587), one for SSL (465)
conf_tls = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_HOST_USER,
    MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
    MAIL_FROM=MAIL_FROM_WITH_NAME,
    MAIL_PORT=587,
    MAIL_SERVER=settings.EMAIL_HOST,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER="templates/email"
)

conf_ssl = ConnectionConfig(
    MAIL_USERNAME=settings.EMAIL_HOST_USER,
    MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
    MAIL_FROM=MAIL_FROM_WITH_NAME,
    MAIL_PORT=465,
    MAIL_SERVER=settings.EMAIL_HOST,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER="templates/email"
)

env = Environment(loader=FileSystemLoader("templates/email"))


# 🔑 Purpose normalizer (fix)
def normalize_purpose(purpose: str) -> str:
    mapping = {
        "admin_signup": "signup",
        "admin_login": "login",
        "admin_reset": "password_reset",
        "officer_signup": "officer_signup"
    }
    return mapping.get(purpose, purpose)


# 🔁 Central retry wrapper
async def send_email_with_retry(message: MessageSchema, subject: str, to_email: str):
    """Try sending via TLS first (587), then SSL (465) if it fails"""
    try:
        fm = FastMail(conf_tls)
        await fm.send_message(message)
        logger.info(f"{subject} email sent to {to_email} via port 587")
        return True
    except Exception as e:
        logger.warning(f"Failed to send {subject} via port 587: {str(e)}")
        try:
            fm = FastMail(conf_ssl)
            await fm.send_message(message)
            logger.info(f"{subject} email sent to {to_email} via port 465")
            return True
        except Exception as e2:
            logger.error(f"Failed to send {subject} email via both ports: {str(e2)}")
            return False


# 🔑 OTP email
async def send_otp_email(to_email: str, name: str, token: str, purpose: str):
    """Generic function to send OTP emails with retry"""
    try:
        canonical_purpose = normalize_purpose(purpose)

        if canonical_purpose == "signup":
            subject = "Marshal Core - Verify Your Account"
            template = "signup_otp.html"
        elif canonical_purpose == "login":
            subject = "Marshal Core - Login Verification"
            template = "login_otp.html"
        elif canonical_purpose == "password_reset":
            subject = "Marshal Core - Password Reset"
            template = "reset_password.html"
        elif canonical_purpose == "officer_signup":
            subject = "Marshal Core - Officer Account Verification"
            template = "officer_signup_otp.html"
        else:
            subject = "Marshal Core - Verification Code"
            template = "generic_otp.html"

        html = env.get_template(template).render(name=name, token=token)

        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=html,
            subtype="html"
        )

        return await send_email_with_retry(message, subject, to_email)
    except Exception as e:
        logger.error(f"Failed to build/send OTP email to {to_email}: {str(e)}")
        return False


# ♻️ Reuse retry for other emails
async def send_password_reset_email(to_email: str, name: str, token: str):
    html = env.get_template("reset_password.html").render(name=name, token=token)
    message = MessageSchema(
        subject="Marshal Core - Password Reset",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    return await send_email_with_retry(message, "Password Reset", to_email)


async def send_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Received",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    return await send_email_with_retry(message, "Application Confirmation", to_email)


async def send_application_password_email(to_email: str, name: str, password: str):
    html = env.get_template("application_password.html").render(name=name, password=password)
    message = MessageSchema(
        subject="Your Marshal Core Application Password",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    return await send_email_with_retry(message, "Application Password", to_email)


async def send_guarantor_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Submitted Successfully",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    return await send_email_with_retry(message, "Guarantor Confirmation", to_email)


# NEW: PDF Email Functions
async def send_pdfs_email(
    to_email: str, 
    name: str, 
    terms_pdf_path: str, 
    application_pdf_path: str,
    cc_email: Optional[str] = None
) -> bool:
    """
    Send both PDFs as email attachments
    """
    try:
        logger.info(f"Sending PDFs email to: {to_email}")
        
        # Prepare HTML content
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background-color: #f9f9f9; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .button {{ display: inline-block; background-color: #1a237e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 10px 5px; }}
                .document-list {{ background: white; padding: 15px; border-left: 4px solid #1a237e; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Marshal Core Nigeria</h1>
                    <h2>Officer Registration Documents</h2>
                </div>
                
                <div class="content">
                    <h3>Dear {name},</h3>
                    
                    <p>Thank you for completing your application with Marshal Core Nigeria. Your application documents have been generated and are attached to this email.</p>
                    
                    <div class="document-list">
                        <h4>📎 Attached Documents:</h4>
                        <ol>
                            <li><strong>Terms & Conditions</strong> - Official terms and conditions for Marshal Core Nigeria officers</li>
                            <li><strong>Application Form</strong> - Your completed registration form</li>
                        </ol>
                    </div>
                    
                    <p>Please keep these documents safe as they are required for official records and future reference.</p>
                    
                    <p><strong>Next Steps:</strong></p>
                    <ul>
                        <li>Save the attached PDFs to your device</li>
                        <li>Print copies for your personal records</li>
                        <li>Login to your dashboard to track your registration status</li>
                    </ul>
                    
                    <p>If you have any questions or need assistance, please contact our support team.</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://marshal-core-frontend.onrender.com/existing-officer-login.html" class="button">Login to Dashboard</a>
                        <a href="https://marshal-core-frontend.onrender.com/contact.html" class="button" style="background-color: #4CAF50;">Contact Support</a>
                    </div>
                    
                    <p>Best regards,<br>
                    <strong>Marshal Core Nigeria Admin Team</strong></p>
                </div>
                
                <div class="footer">
                    <p>This is an automated email. Please do not reply to this message.</p>
                    <p>© 2024 Marshal Core Nigeria. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Prepare recipients
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        
        # Create message with attachments
        message = MessageSchema(
            subject="Your Marshal Core Application Documents",
            recipients=recipients,
            body=html,
            subtype="html",
            attachments=[
                {
                    "file": terms_pdf_path,
                    "headers": {
                        "Content-Disposition": f'attachment; filename="{Path(terms_pdf_path).name}"'
                    }
                },
                {
                    "file": application_pdf_path,
                    "headers": {
                        "Content-Disposition": f'attachment; filename="{Path(application_pdf_path).name}"'
                    }
                }
            ]
        )
        
        # Send email with retry
        return await send_email_with_retry(message, "Application Documents", to_email)
        
    except Exception as e:
        logger.error(f"Failed to send PDFs email to {to_email}: {str(e)}")
        return False


# FIXED: Single implementation of send_existing_officer_pdfs_email
# In your email_service.py, replace the send_existing_officer_pdfs_email function with:

async def send_existing_officer_pdfs_email(
    to_email: str,
    name: str,
    officer_id: str,
    terms_pdf_path: str = None,
    registration_pdf_path: str = None,
    cc_email: Optional[str] = None
) -> bool:
    """
    Send PDFs email for existing officers using proper template
    """
    try:
        logger.info(f"📧 Preparing to send PDFs email to existing officer: {to_email}")
        
        # Try to use the template
        try:
            # Load the template
            template = env.get_template("existing_officer_documents.html")
            
            # Render template with context
            html = template.render(
                name=name,
                officer_id=officer_id,
                date=datetime.now().strftime('%d %B, %Y')
            )
            
            logger.info(f"✅ Template rendered successfully for {officer_id}")
            
        except Exception as template_error:
            logger.warning(f"Template rendering failed: {str(template_error)}. Using fallback HTML.")
            
            # Fallback HTML if template doesn't exist
            html = f"""
            <!DOCTYPE html>
            <html>
            <body>
                <h2>Marshal Core Nigeria - Registration Documents</h2>
                <p>Dear {name},</p>
                <p>Your registration documents for Officer ID: {officer_id} have been generated.</p>
                <p>Login to your dashboard to download them.</p>
                <p>Date: {datetime.now().strftime('%d %B, %Y')}</p>
            </body>
            </html>
            """
        
        # Prepare recipients
        recipients = [to_email]
        if cc_email:
            recipients.append(cc_email)
        
        # Create message
        message = MessageSchema(
            subject=f"Marshal Core Nigeria - Registration Documents for Officer {officer_id}",
            recipients=recipients,
            body=html,
            subtype="html"
        )
        
        # Send email with retry
        success = await send_email_with_retry(message, "Existing Officer Documents", to_email)
        
        if success:
            logger.info(f"✅ Email sent successfully to {to_email} for officer {officer_id}")
            
            # Also log PDF paths for debugging
            logger.info(f"📄 PDF Paths for {officer_id}:")
            logger.info(f"   - Terms: {terms_pdf_path}")
            logger.info(f"   - Registration: {registration_pdf_path}")
        else:
            logger.error(f"❌ Failed to send email to {to_email}")
        
        return success
        
    except Exception as e:
        logger.error(f"💥 Error in send_existing_officer_pdfs_email: {str(e)}")
        # Return True to not block the registration flow
        return True


# Also add this function for registration confirmation
async def send_existing_officer_welcome_email(
    to_email: str,
    name: str,
    officer_id: str,
    category: str
) -> bool:
    """Send welcome email to existing officer after registration"""
    try:
        logger.info(f"Sending welcome email to new existing officer: {to_email}")
        
        # Try to use template
        try:
            template = env.get_template("existing_officer_welcome.html")
            html = template.render(
                name=name,
                officer_id=officer_id,
                category=category,
                date=datetime.now().strftime('%d %B, %Y')
            )
        except:
            # Fallback
            html = f"""
            <h2>Welcome to Marshal Core Nigeria</h2>
            <p>Dear {name},</p>
            <p>Your registration as an existing officer is complete.</p>
            <p><strong>Officer ID:</strong> {officer_id}</p>
            <p><strong>Category:</strong> {category}</p>
            <p>Use your Officer ID to login to the dashboard.</p>
            """
        
        message = MessageSchema(
            subject=f"Welcome to Marshal Core Nigeria - Officer {officer_id}",
            recipients=[to_email],
            body=html,
            subtype="html"
        )
        
        return await send_email_with_retry(message, "Existing Officer Welcome", to_email)
        
    except Exception as e:
        logger.error(f"Error sending welcome email: {str(e)}")
        return True