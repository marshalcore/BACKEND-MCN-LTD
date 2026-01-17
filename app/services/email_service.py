# app/services/email_service.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import settings
from jinja2 import Environment, FileSystemLoader
import logging
from datetime import datetime
from typing import Optional, List
from pathlib import Path
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl

logger = logging.getLogger(__name__)

# ✅ Always include a professional display name
MAIL_FROM_WITH_NAME = f"Marshal Core <{settings.EMAIL_FROM}>"

# 🔄 ALL SMTP PORT CONFIGURATIONS
SMTP_CONFIGS = [
    # Primary: TLS on port 587 (most common)
    {
        "name": "tls_587",
        "config": ConnectionConfig(
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
    },
    # Secondary: SSL on port 465
    {
        "name": "ssl_465",
        "config": ConnectionConfig(
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
    },
    # Alternative: Port 25 (standard SMTP)
    {
        "name": "plain_25",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=25,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Alternative: Port 2525 (common alternative)
    {
        "name": "tls_2525",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=2525,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    },
    # Alternative: Port 8025 (development/common alt)
    {
        "name": "tls_8025",
        "config": ConnectionConfig(
            MAIL_USERNAME=settings.EMAIL_HOST_USER,
            MAIL_PASSWORD=settings.EMAIL_HOST_PASSWORD,
            MAIL_FROM=MAIL_FROM_WITH_NAME,
            MAIL_PORT=8025,
            MAIL_SERVER=settings.EMAIL_HOST,
            MAIL_STARTTLS=True,
            MAIL_SSL_TLS=False,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
            TEMPLATE_FOLDER="templates/email"
        )
    }
]

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

# 🚀 CONCURRENT PORT TESTING
async def test_smtp_connection_async(host: str, port: int, use_tls: bool = False, use_ssl: bool = False) -> bool:
    """Test SMTP connection to a specific port"""
    try:
        smtp = aiosmtplib.SMTP(
            hostname=host,
            port=port,
            use_tls=use_ssl,  # SSL is immediate TLS
            start_tls=use_tls,  # STARTTLS (upgrade after connection)
            timeout=5
        )
        
        await smtp.connect()
        
        if use_tls and not use_ssl:
            await smtp.starttls()
        
        await smtp.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        await smtp.quit()
        
        logger.info(f"✅ SMTP connection successful on port {port}")
        return True
    except Exception as e:
        logger.debug(f"❌ SMTP connection failed on port {port}: {str(e)}")
        return False

async def find_best_smtp_port() -> Optional[ConnectionConfig]:
    """Test all ports concurrently and return the first working one"""
    tasks = []
    
    # Test all ports concurrently
    for config in SMTP_CONFIGS:
        port = config["config"].MAIL_PORT
        use_tls = config["config"].MAIL_STARTTLS
        use_ssl = config["config"].MAIL_SSL_TLS
        
        task = test_smtp_connection_async(
            settings.EMAIL_HOST,
            port,
            use_tls,
            use_ssl
        )
        tasks.append((config, task))
    
    # Wait for the first successful connection
    for config, task in tasks:
        try:
            success = await asyncio.wait_for(task, timeout=10)
            if success:
                logger.info(f"🎯 Selected SMTP port {config['config'].MAIL_PORT} ({config['name']})")
                return config["config"]
        except (asyncio.TimeoutError, Exception):
            continue
    
    logger.error("❌ All SMTP ports failed")
    return None

# 🔁 CENTRAL RETRY WRAPPER WITH CONCURRENT PORT TESTING
async def send_email_with_retry(message: MessageSchema, subject: str, to_email: str) -> bool:
    """Send email using the best available SMTP port with concurrent testing"""
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Find best port for this attempt
            best_config = await find_best_smtp_port()
            
            if not best_config:
                logger.error(f"❌ No working SMTP port found on attempt {attempt + 1}")
                await asyncio.sleep(retry_delay)
                continue
            
            # Send email with selected config
            fm = FastMail(best_config)
            await fm.send_message(message)
            
            logger.info(f"✅ {subject} email sent to {to_email} via port {best_config.MAIL_PORT}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt + 1} failed for {subject} to {to_email}: {str(e)}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    logger.error(f"❌ Failed to send {subject} email to {to_email} after {max_retries} attempts")
    return False

# 📧 EMAIL QUEUE SYSTEM (Decoupling PDF from Email)
class EmailQueue:
    """Simple in-memory email queue with retry logic"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.failed_queue = asyncio.Queue()
        self.is_processing = False
    
    async def add_email(self, message: MessageSchema, subject: str, to_email: str):
        """Add email to queue"""
        await self.queue.put({
            "message": message,
            "subject": subject,
            "to_email": to_email,
            "attempts": 0,
            "max_attempts": 3,
            "added_at": datetime.now()
        })
        logger.info(f"📨 Email queued for {to_email}: {subject}")
    
    async def process_queue(self):
        """Process email queue in background"""
        if self.is_processing:
            return
        
        self.is_processing = True
        logger.info("🚀 Starting email queue processor")
        
        while True:
            try:
                # Get email from queue (with timeout)
                try:
                    email_item = await asyncio.wait_for(self.queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    # No emails, check failed queue
                    await self.retry_failed_emails()
                    continue
                
                # Try to send
                success = await send_email_with_retry(
                    email_item["message"],
                    email_item["subject"],
                    email_item["to_email"]
                )
                
                if success:
                    logger.info(f"✅ Queued email sent: {email_item['subject']} to {email_item['to_email']}")
                else:
                    # Move to failed queue for retry
                    email_item["attempts"] += 1
                    if email_item["attempts"] < email_item["max_attempts"]:
                        # Schedule retry with exponential backoff
                        retry_delay = 60 * (2 ** email_item["attempts"])  # 1min, 2min, 4min
                        email_item["retry_at"] = datetime.now().timestamp() + retry_delay
                        await self.failed_queue.put(email_item)
                        logger.warning(f"⚠️ Email moved to retry queue: {email_item['subject']} (attempt {email_item['attempts']})")
                    else:
                        logger.error(f"❌ Email permanently failed: {email_item['subject']} to {email_item['to_email']}")
                
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Error in email queue processor: {str(e)}")
                await asyncio.sleep(5)
    
    async def retry_failed_emails(self):
        """Retry failed emails"""
        retry_items = []
        current_time = datetime.now().timestamp()
        
        # Collect items ready for retry
        while not self.failed_queue.empty():
            try:
                item = self.failed_queue.get_nowait()
                if item.get("retry_at", 0) <= current_time:
                    retry_items.append(item)
                else:
                    # Put back if not ready
                    await self.failed_queue.put(item)
            except asyncio.QueueEmpty:
                break
        
        # Retry collected items
        for item in retry_items:
            logger.info(f"🔄 Retrying email: {item['subject']} (attempt {item['attempts'] + 1})")
            await self.queue.put(item)

# Global email queue instance
email_queue = EmailQueue()

# 🔑 OTP email
async def send_otp_email(to_email: str, name: str, token: str, purpose: str):
    """Generic function to send OTP emails via queue"""
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

        # Queue email instead of sending directly
        await email_queue.add_email(message, subject, to_email)
        return True
        
    except Exception as e:
        logger.error(f"Failed to build OTP email for {to_email}: {str(e)}")
        # Still return True to not block user flow
        return True

# ♻️ Reuse retry for other emails
async def send_password_reset_email(to_email: str, name: str, token: str):
    html = env.get_template("reset_password.html").render(name=name, token=token)
    message = MessageSchema(
        subject="Marshal Core - Password Reset",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Password Reset", to_email)
    return True

async def send_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Received",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Application Confirmation", to_email)
    return True

async def send_application_password_email(to_email: str, name: str, password: str):
    html = env.get_template("application_password.html").render(name=name, password=password)
    message = MessageSchema(
        subject="Your Marshal Core Application Password",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Application Password", to_email)
    return True

async def send_guarantor_confirmation_email(to_email: str, name: str):
    html = env.get_template("confirm_submission.html").render(name=name, link="/static/guarantor-form.pdf")
    message = MessageSchema(
        subject="Marshal Core Application Submitted Successfully",
        recipients=[to_email],
        body=html,
        subtype="html"
    )
    await email_queue.add_email(message, "Guarantor Confirmation", to_email)
    return True

# NEW: PDF Email Functions - DECOUPLED VERSION
async def send_pdfs_email(
    to_email: str, 
    name: str, 
    terms_pdf_path: str, 
    application_pdf_path: str,
    cc_email: Optional[str] = None
) -> bool:
    """
    Queue PDF email for sending (decoupled from PDF generation)
    """
    try:
        logger.info(f"📨 Queueing PDFs email to: {to_email}")
        
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
        
        # Queue email (decoupled from PDF generation)
        await email_queue.add_email(message, "Application Documents", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to queue PDFs email for {to_email}: {str(e)}")
        # Return True to not block PDF generation
        return True

async def send_existing_officer_pdfs_email(
    to_email: str,
    name: str,
    officer_id: str,
    terms_pdf_path: str = None,
    registration_pdf_path: str = None,
    cc_email: Optional[str] = None
) -> bool:
    """
    Queue existing officer PDFs email (decoupled)
    """
    try:
        logger.info(f"📨 Queueing PDFs email for existing officer: {to_email}")
        
        # Try to use template
        try:
            template = env.get_template("existing_officer_documents.html")
            html = template.render(
                name=name,
                officer_id=officer_id,
                date=datetime.now().strftime('%d %B, %Y')
            )
        except Exception as template_error:
            logger.warning(f"Template rendering failed: {str(template_error)}")
            # Fallback HTML
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
        
        # Queue email
        await email_queue.add_email(message, "Existing Officer Documents", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error queueing existing officer email: {str(e)}")
        return True

async def send_existing_officer_welcome_email(
    to_email: str,
    name: str,
    officer_id: str,
    category: str
) -> bool:
    """Queue welcome email for existing officer"""
    try:
        logger.info(f"Queueing welcome email for existing officer: {to_email}")
        
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
        
        await email_queue.add_email(message, "Existing Officer Welcome", to_email)
        return True
        
    except Exception as e:
        logger.error(f"Error queueing welcome email: {str(e)}")
        return True

# PAYMENT RECEIPT EMAIL - ADDED THIS FUNCTION
async def send_payment_receipt_email(
    to_email: str,
    name: str,
    payment_reference: str,
    amount: int,
    payment_type: str,
    paid_at: datetime = None,
    payment_method: str = None
) -> bool:
    """
    Send payment receipt email
    """
    try:
        logger.info(f"Queueing payment receipt email to: {to_email}")
        
        # Format the date
        payment_date = paid_at.strftime('%d %B, %Y %I:%M %p') if paid_at else datetime.now().strftime('%d %B, %Y %I:%M %p')
        
        # Try to use template if available
        try:
            template = env.get_template("payment_receipt.html")
            html = template.render(
                name=name,
                payment_reference=payment_reference,
                amount=amount,
                payment_type=payment_type,
                payment_date=payment_date,
                payment_method=payment_method or "Online Payment"
            )
        except Exception as template_error:
            logger.warning(f"Payment receipt template not found: {str(template_error)}")
            # Fallback HTML
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 30px; background-color: #f9f9f9; }}
                    .receipt {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
                    .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                    .amount {{ font-size: 24px; color: #1a237e; font-weight: bold; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Marshal Core Nigeria</h1>
                        <h2>Payment Receipt</h2>
                    </div>
                    
                    <div class="content">
                        <h3>Dear {name},</h3>
                        
                        <p>Thank you for your payment. Your transaction has been completed successfully.</p>
                        
                        <div class="receipt">
                            <h4>Payment Details:</h4>
                            <p><strong>Reference Number:</strong> {payment_reference}</p>
                            <p><strong>Payment Type:</strong> {payment_type}</p>
                            <p><strong>Payment Method:</strong> {payment_method or 'Online Payment'}</p>
                            <p><strong>Date:</strong> {payment_date}</p>
                            <p><strong>Amount:</strong> <span class="amount">₦{amount:,.2f}</span></p>
                            <p><strong>Status:</strong> <span style="color: #4CAF50; font-weight: bold;">✓ Completed</span></p>
                        </div>
                        
                        <p>This receipt confirms that your payment has been received and processed successfully.</p>
                        
                        <p>Please keep this receipt for your records. You can also download it from your dashboard.</p>
                        
                        <p>If you have any questions about this payment, please contact our support team.</p>
                        
                        <p>Best regards,<br>
                        <strong>Marshal Core Nigeria Finance Team</strong></p>
                    </div>
                    
                    <div class="footer">
                        <p>This is an automated email. Please do not reply to this message.</p>
                        <p>© 2024 Marshal Core Nigeria. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """
        
        # Create message
        message = MessageSchema(
            subject=f"Payment Receipt - {payment_reference}",
            recipients=[to_email],
            body=html,
            subtype="html"
        )
        
        # Queue email
        await email_queue.add_email(message, "Payment Receipt", to_email)
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to queue payment receipt email for {to_email}: {str(e)}")
        # Return True to not block payment flow
        return True

# 🚀 Start email queue processor on module import
async def start_email_queue():
    """Start the email queue processor"""
    asyncio.create_task(email_queue.process_queue())
    logger.info("📧 Email queue processor started")

# Initialize when module is imported
import asyncio
loop = asyncio.get_event_loop()
if loop.is_running():
    asyncio.create_task(start_email_queue())
else:
    loop.run_until_complete(start_email_queue())