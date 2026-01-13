# app/routes/payment.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.payment import ManualPaymentRequest, GatewayCallback
from app.services.payment_service import process_payment_success, verify_paystack_payment, verify_flutterwave_payment
from app.utils.promote_applicant import promote_to_applicant
from sqlalchemy import func
from app.models.pre_applicant import PreApplicant

router = APIRouter(prefix="/payment", tags=["Payment"])

@router.post("/manual/confirm")
async def manual_payment(data: ManualPaymentRequest, db: Session = Depends(get_db)):
    return await process_payment_success(data.email, db)

@router.post("/paystack/verify")
async def paystack_verify(data: GatewayCallback, db: Session = Depends(get_db)):
    print("\U0001F680 Paystack verify endpoint hit")
    
    # Check if payment was already processed
    normalized_email = data.email.strip().lower()
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if pre_applicant and pre_applicant.has_paid:
        return {"message": "Payment already verified. Please check email to continue registration."}
    
    if not verify_paystack_payment(data.reference):
        raise HTTPException(status_code=400, detail="Paystack verification failed")

    await process_payment_success(data.email, db)
    promote_to_applicant(data.email, db)

    return {"message": "Payment verified successfully. Please check email to continue registration."}

@router.post("/flutterwave/verify")
async def flutterwave_verify(data: GatewayCallback, db: Session = Depends(get_db)):
    # Check if payment was already processed
    normalized_email = data.email.strip().lower()
    pre_applicant = db.query(PreApplicant).filter(
        func.lower(PreApplicant.email) == normalized_email
    ).first()
    
    if pre_applicant and pre_applicant.has_paid:
        return {"message": "Payment already verified."}
    
    if not verify_flutterwave_payment(data.reference):
        raise HTTPException(status_code=400, detail="Flutterwave verification failed")

    await process_payment_success(data.email, db)
    promote_to_applicant(data.email, db)

    return {"message": "Payment verified successfully."}