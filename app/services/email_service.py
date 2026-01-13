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
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background-color: #2c3e50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
                    <h1>Marshal Core Nigeria</h1>
                    <p>Official Security Services Provider</p>
                </div>
                
                <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px;">
                    <h2>Dear {name},</h2>
                    
                    <p>Thank you for completing your application with Marshal Core Nigeria. Your application documents have been generated and are attached to this email.</p>
                    
                    <div style="background-color: #e8f4fc; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0;">
                        <h3>📎 Attached Documents:</h3>
                        <ol>
                            <li><strong>Terms & Conditions</strong> - Legal agreement outlining your rights and responsibilities</li>
                            <li><strong>Application Form</strong> - Complete summary of your application for your records</li>
                        </ol>
                    </div>
                    
                    <h3>📋 Important Next Steps:</h3>
                    <ol>
                        <li>Review both documents carefully</li>
                        <li>Print a copy of your Application Form for your records</li>
                        <li>Read and understand the Terms & Conditions thoroughly</li>
                        <li>Keep these documents in a safe place</li>
                    </ol>
                    
                    <p>If you have any questions about your documents, please contact our support team at <a href="mailto:support@marshalcoreng.com">support@marshalcoreng.com</a>.</p>
                    
                    <p>Best regards,<br>
                    <strong>The Marshal Core Nigeria Team</strong></p>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #777; text-align: center;">
                    <p>Marshal Core Nigeria Limited | RC: 1234567</p>
                    <p>Generated on: {datetime.now().strftime('%d %B, %Y')}</p>
                    <p>This is an automated message. Please do not reply to this email.</p>
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