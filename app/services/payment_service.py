import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.pre_applicant import PreApplicant  # ✅ switched from Applicant
from app.utils.password import generate_password
from app.services.email_service import send_application_password_email
from app.config import settings


async def process_payment_success(email: str, db: Session):
    print(f"🔍 Looking for pre-applicant with email: {email}")
    pre_applicant = db.query(PreApplicant).filter(PreApplicant.email == email).first()

    if not pre_applicant:
        print("❌ PreApplicant not found.")
        raise HTTPException(status_code=404, detail="PreApplicant not found")

    # Check if already paid
    if pre_applicant.has_paid:
        print("✅ Already marked as paid.")
        return {"message": "Already paid."}

    # ✅ Prevent duplicate password generation
    if pre_applicant.application_password:
        print("⚠️ Password already generated, skipping regeneration.")
    else:
        password = generate_password()
        pre_applicant.application_password = password
        print(f"📧 Sending password email to {email}")
        await send_application_password_email(email, pre_applicant.full_name, password)

    pre_applicant.has_paid = True
    db.commit()

    return {"message": "Payment verified. Password sent if not already generated."}



def verify_paystack_payment(reference: str) -> bool:
    headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}
    url = f"https://api.paystack.co/transaction/verify/{reference}"

    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()

        data = response.json().get("data", {})
        return data.get("status") == "success"

    except httpx.RequestError as e:
        print(f"[Paystack] Request error: {e}")
        return False
    except httpx.HTTPStatusError as e:
        print(f"[Paystack] HTTP error: {e}")
        return False
    except Exception as e:
        print(f"[Paystack] Unknown error: {e}")
        return False


def verify_flutterwave_payment(reference: str) -> bool:
    headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}
    url = f"https://api.flutterwave.com/v3/transactions/{reference}/verify"

    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()

        data = response.json().get("data", {})
        return data.get("status") == "successful"

    except httpx.RequestError as e:
        print(f"[Flutterwave] Request error: {e}")
        return False
    except httpx.HTTPStatusError as e:
        print(f"[Flutterwave] HTTP error: {e}")
        return False
    except Exception as e:
        print(f"[Flutterwave] Unknown error: {e}")
        return False
