# Marshal Core of Nigeria - Backend Implementation Guide

## 📋 CURRENT STATUS

| Component | Status | Mode |
|-----------|--------|------|
| **Paystack Integration** | ✅ Active | **TEST MODE** (not live) |
| **Payment Processing** | ✅ Working | Test money |
| **Split Configuration** | ✅ Built | Manual (not native) |
| **PDF Generation** | ✅ Working | - |
| **Email System** | ✅ Working | Resend API |

---

## 🎯 TO SWITCH TO LIVE MODE

### Step 1: Update Environment Variables on Render.com

Set these environment variables:

```bash
PAYSTACK_SECRET_KEY=sk_live_xxxxx          # Replace with LIVE secret key
PAYSTACK_PUBLIC_KEY=pk_live_xxxxx           # Replace with LIVE public key
PAYSTACK_SPLIT_CODE=SPL_KRGO7FYBBU         # Your Paystack Dashboard Split Group
```

### Step 2: Enable Native Split in Code

**File**: `app/routes/payment.py`
**Line**: ~359

**Change FROM:**
```python
# Priority 1: Use Dashboard Split Code from settings if set
if False and settings.PAYSTACK_SPLIT_CODE:
```

**Change TO:**
```python
# Priority 1: Use Dashboard Split Code from settings if set
if settings.PAYSTACK_SPLIT_CODE:
```

This will enable Paystack's native split feature, automatically distributing:
- 50% → MARSHAL OF NIGERIA LIMITED (KUDA Bank)
- 35% → OSEOBOH JOSHUA EROMONSELE (UBA)
- 15% → ESTECH DIGITAL SYSTEMS LIMITED (FCMB)

### Step 3: Verify Payment Mode

**File**: `app/services/payment_service.py`
**Line**: ~50

Ensure:
```python
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
is_test_mode = "sk_test_" in PAYSTACK_SECRET_KEY
```

---

## 📁 KEY FILES

| File | Location | Purpose |
|------|----------|---------|
| Payment Routes | `app/routes/payment.py` | Payment initiation & verification |
| PDF Service | `app/services/pdf_service.py` | PDF generation with stamps |
| Config | `app/config.py` | Configuration settings |
| Payment Service | `app/services/payment_service.py` | Paystack API wrapper |

---

## 🔧 PDF STAMP SYSTEM

### Current Implementation

| Document | Page 1 | Page 2 | Page 3 |
|----------|--------|--------|--------|
| **Terms & Conditions** | Footer stamp | Footer stamp | Inline with commandant |
| **Application Form** | Footer stamp | Inline with commandant | - |

### Stamp Logic (in `pdf_service.py`)

```python
# Footer stamp - shows on pages 1, 2 (not last page)
current_page = canvas_obj._pageNumber
if self.stamp_bytes and current_page < total_pages:
    # Draw stamp at bottom RIGHT
```

### To Modify Stamp Position

**File**: `app/services/pdf_service.py`
**Function**: `_create_header_footer()`
**Lines**: ~323-340

Current position:
```python
stamp_x = page_width - doc.rightMargin - stamp_width - 0.15*inch  # Bottom RIGHT
stamp_y = 1.2 * inch  # Above footer line
```

---

## 💰 PAYMENT CONFIGURATION

### Payment Types & Amounts

| Type | Amount | Reference Format |
|------|--------|------------------|
| Regular | ₦5,180 | `MCN_REGULAR_{timestamp}` |
| VIP | ₦25,900 | `MCN_VIP_{timestamp}` |

### Split Distribution

```python
SPLIT_RECIPIENTS = {
    "marshal_core_share": 0.50,      # 50% - Marshal Core of Nigeria Ltd
    "systems_maintainance": 0.35,    # 35% - Oseoboh Joshua Eromonsele
    "estech_digital_systems_limited": 0.15  # 15% - ESTECH Digital Systems Ltd
}
```

### Paystack Split Group (Dashboard)

```
Split Code: SPL_KRGO7FYBBU
Type: Percentage Split
Currency: NGN

Subaccounts:
- MARSHAL CORE OF NIGERIA LIMITED (50%) - United Bank For Africa
- ESTECH DIGITAL SYSTEMS LIMITED (15%) - First City Monument Bank
- OSEOBOH JOSHUA EROMONSELE (35%) - First City Monument Bank
```

---

## 🧪 TESTING CHECKLIST

### Before Live Mode

- [ ] Test regular payment (₦5,180) end-to-end
- [ ] Test VIP payment (₦25,900) end-to-end
- [ ] Verify PDF stamps appear correctly on all pages
- [ ] Verify payment_type stored correctly in database
- [ ] Verify email notifications sent
- [ ] Check payment duplication issue is fixed

### After Switching to Live

- [ ] Enable `PAYSTACK_SPLIT_CODE` in environment
- [ ] Enable split code in `payment.py` (change line 359)
- [ ] Test with small amounts first
- [ ] Verify split transfers execute correctly
- [ ] Monitor payment reports in Paystack Dashboard

---

## 🌐 API ENDPOINTS

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/payments/initiate` | POST | Start payment |
| `/api/payments/verify/{ref}` | POST | Verify payment |
| `/pre-applicant/check-status` | POST | Check registration status |
| `/pre-applicant/select-tier` | POST | Select payment tier |
| `/apply` | POST | Submit application |
| `/pdf/application/{id}` | GET | Download application PDF |
| `/pdf/terms/{id}` | GET | Download terms PDF |
| `/api/health` | GET | Health check |

---

## 🔐 SECURITY NOTES

1. **Never commit** Paystack keys to version control
2. **Use environment variables** for all secrets
3. **Webhook URL**: Set in Paystack Dashboard for payment callbacks
4. **Callback URL**: `https://marshalcoreofnigeria.ng/apply.html?payment_success=true`

---

## 📧 EMAIL CONFIGURATION

**Provider**: Resend
**From**: `onboarding@marshalcoreofnigeria.ng`

**Email Templates**:
- Application Password
- Payment Receipt
- Applicant Documents (with PDF attachments)
- Guarantor Request

---

## 🗄️ DATABASE

**Provider**: Neon PostgreSQL
**Region**: eu-west-2 (AWS)

### Key Tables:
- `payments` - All payment transactions
- `pre_applicants` - New registrations
- `applicants` - Completed applications
- `officers` - Existing officers

---

## 🚀 DEPLOYMENT

**Platform**: Render.com
**Region**: EU-West

### Deploy Steps:
1. Push to GitHub main branch
2. Render auto-deploys
3. Health check at: `https://api.marshalcoreofnigeria.ng/api/health`

---

## 📞 SUPPORT CONTACTS

| Role | Name | Bank | Account |
|------|------|------|---------|
| Marshal Core | MARSHAL OF NIGERIA LIMITED | KUDA Bank | - |
| Systems | OSEOBOH JOSHUA EROMONSELE | UBA | 2104644267 |
| eSTech | ESTECH DIGITAL SYSTEMS LIMITED | FCMB | 1047085433 |

---

## ❓ TROUBLESHOOTING

### Payment not found
- Check Paystack Dashboard for payment status
- Verify Paystack keys are correct
- Check database for pending payments

### PDF not generating
- Check logo and stamp files exist in `/opt/render/project/src/static/`
- Verify ReportLab is installed
- Check logs for errors

### Email not sending
- Verify Resend API key
- Check email address validity
- Check spam folder

---

**Last Updated**: July 17, 2026
**Version**: 1.0.0
