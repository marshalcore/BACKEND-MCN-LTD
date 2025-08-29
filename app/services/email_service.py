from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from app.config import settings
from jinja2 import Environment, FileSystemLoader
import logging

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
            template = "officer_signup_otp.html"  # add template if needed
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
