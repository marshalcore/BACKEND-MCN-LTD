# Backend API Integration Documentation
## Marshal Core of Nigeria - Recruitment Portal

> **To Frontend Agent:** This is the official Backend API documentation. Please use this as the source of truth for integration.

---

## 🌐 API Overview

| Environment | Base URL |
|-------------|----------|
| **Production** | `https://api.marshalcoreofnigeria.ng` |
| **Frontend** | `https://marshalcoreofnigeria.ng` |

### API Authentication
- **Token-based authentication** via Bearer tokens
- Tokens stored after verification
- Token included in `Authorization: Bearer <token>` header for protected routes

### CORS Configuration
- Allowed origins: `marshalcoreofnigeria.ng`, `*.netlify.app`, `*.marshalcoreofnigeria.ng`
- Preflight OPTIONS requests are handled automatically

---

## 📁 Application Tiers/Categories

| Category | Amount (₦) | Payment Type Key |
|----------|------------|------------------|
| **Regular Cadre** | ₦5,180 | `regular` |
| **VIP Cadre** | ₦25,900 | `vip` |

> **Note:** Use `payment_type` as `regular` or `vip`. Backend already accepts these values.

---

## 🔗 Pre-Applicant Endpoints

Base URL: `https://api.marshalcoreofnigeria.ng/pre-applicant`

### 1. Check Application Status
**POST** `/pre-applicant/check-status`

```json
// Request
{
  "email": "user@example.com"
}

// Success Response (200)
{
  "status": "new",
  "preApplicantId": "string|null",
  "applicantId": "string|null",
  "fullName": "string",
  "email": "string",
  "category": "string|null",
  "hasPassword": false,
  "lastUpdated": "2024-01-01T00:00:00Z"
}
```

### 2. Register Pre-Applicant
**POST** `/pre-applicant/register`

```json
// Request
{
  "fullName": "John Doe",
  "email": "user@example.com",
  "category": "regular"  // "regular" or "vip"
}

// Success Response (201)
{
  "success": true,
  "preApplicantId": "string",
  "message": "Pre-registration successful"
}
```

### 3. Select Tier
**POST** `/pre-applicant/select-tier`

```json
// Request
{
  "email": "user@example.com",
  "category": "regular"  // "regular" or "vip"
}

// Success Response (200)
{
  "success": true,
  "tier": {
    "name": "regular",
    "amount": 518000,  // Amount in KOBO (₦5,180)
    "description": "Foundation Membership"
  }
}
```

### 4. Get Status by Email
**GET** `/pre-applicant/status/{email}`

```json
// Success Response (200)
{
  "preApplicantId": "string",
  "email": "user@example.com",
  "fullName": "John Doe",
  "category": "regular",
  "status": "pending_payment",
  "hasPassword": false,
  "applicationStatus": "pending_payment"
}
```

---

## 💰 Payment Endpoints

Base URL: `https://api.marshalcoreofnigeria.ng/api/payments`

### 1. Initiate Payment
**POST** `/api/payments/initiate`

```json
// Request
{
  "email": "user@example.com",
  "payment_type": "regular",  // "regular" or "vip"
  "user_type": "pre_applicant"   // "pre_applicant", "applicant", "officer", "existing_officer"
}

// Success Response (200)
{
  "success": true,
  "reference": "MCN_xxxxx_xxxxx",
  "authorizationUrl": "https://checkout.paystack.com/xxxxx",
  "amount": 518000,  // In KOBO
  "currency": "NGN"
}
```

### 2. Verify Payment
**GET** `/api/payments/verify/{reference}`

```json
// Success Response (200)
{
  "success": true,
  "verified": true,
  "reference": "MCN_xxxxx_xxxxx",
  "amount": 518000,
  "status": "success",
  "message": "Payment verified successfully",
  "preApplicantId": "string"
}
```

### 3. Payment Callback (Paystack)
**POST** `/api/payments/callback/paystack`

This endpoint is called by Paystack after payment completion (configured in Paystack dashboard).

### 4. Get User Payments
**GET** `/api/payments/user/{email}`

```json
// Success Response (200)
{
  "payments": [
    {
      "id": "string",
      "reference": "MCN_xxxxx",
      "amount": 518000,
      "status": "success",
      "payment_type": "regular",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### 5. Get Payment Types
**GET** `/api/payments/types`

```json
// Success Response (200)
{
  "payment_types": {
    "regular": {
      "name": "Foundation Membership",
      "amount": 518000,
      "amount_display": "₦5,180"
    },
    "vip": {
      "name": "VIP Membership",
      "amount": 2590000,
      "amount_display": "₦25,900"
    }
  }
}
```

### 6. Check Payment by Email
**GET** `/api/payments/check/{email}`

```json
// Success Response (200)
{
  "has_paid": true,
  "payment": {
    "reference": "MCN_xxxxx",
    "amount": 518000,
    "status": "success"
  }
}
```

---

## 🔐 Application Access Endpoints

Base URL: `https://api.marshalcoreofnigeria.ng/access`

### 1. Generate Password
**POST** `/access/generate-password`

```json
// Request
{
  "email": "user@example.com"
}

// Success Response (200)
{
  "success": true,
  "message": "Password has been sent to your email"
}
```

### 2. Verify Password/Token
**POST** `/access/verify`

```json
// Request
{
  "email": "user@example.com",
  "password": "user_password"
}

// Success Response (200)
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "expiresIn": 1440,
  "expiresAt": "2024-01-02T00:00:00Z"
}
```

### 3. Check Access Status
**POST** `/access/check-status`

```json
// Request
{
  "email": "user@example.com"
}

// Success Response (200)
{
  "hasPassword": true,
  "email": "user@example.com",
  "preApplicantId": "string"
}
```

---

## 📝 Application Form Endpoints

Base URL: `https://api.marshalcoreofnigeria.ng/apply`

### 1. Submit Application
**POST** `/apply`

```json
// Request (multipart/form-data)
{
  "email": "user@example.com",
  "fullName": "John Doe",
  "phone": "+234xxxxxxxxxx",
  "dateOfBirth": "1990-01-01",
  "gender": "male",
  "address": "123 Street, City, State",
  "state": "Lagos",
  "localGovernment": "Agege",
  "occupation": "Developer",
  "reason": "Why I want to join MCN",
  "passportPhoto": "<file>",
  "ninSlip": "<file>",
  "validId": "<file>"
}

// Success Response (200)
{
  "success": true,
  "applicantId": "string",
  "status": "submitted",
  "message": "Application submitted successfully"
}
```

---

## 📋 Privacy Notice Endpoints

Base URL: `https://api.marshalcoreofnigeria.ng/privacy`

### 1. Accept Privacy Notice
**POST** `/privacy/accept`

```json
// Request
{
  "email": "user@example.com",
  "accepted": true
}

// Success Response (200)
{
  "success": true,
  "message": "Privacy notice accepted"
}
```

---

## 💾 Save Progress Endpoints

### 1. Save Application Progress
**POST** `/save-progress`

```json
// Request
{
  "email": "user@example.com",
  "section": 1,
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}

// Success Response (200)
{
  "success": true,
  "lastSaved": "2024-01-01T00:00:00Z"
}
```

### 2. Get Application Progress
**GET** `/get-progress/{email}`

```json
// Success Response (200)
{
  "email": "user@example.com",
  "progress": {
    "1": { "field1": "value1" },
    "2": { "field2": "value2" }
  },
  "lastSaved": "2024-01-01T00:00:00Z"
}
```

---

## 🔧 Health Check Endpoint

**GET** `https://api.marshalcoreofnigeria.ng/`

```json
// Success Response (200)
{
  "status": "healthy",
  "service": "Marshal Core API",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**GET** `/api/health`

```json
// Success Response (200)
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## ⚠️ Error Handling

### Standard Error Response Format
```json
// Validation errors
{
  "detail": "Error message string"
}

// Array errors
[
  { "msg": "Field is required", "loc": ["body", "field"] }
]

// HTTP Status Codes
400 - Bad Request (validation errors)
401 - Unauthorized (invalid/expired token)
404 - Not Found
500 - Internal Server Error
```

### Network Error Handling
- `Failed to fetch` - Network connectivity issues
- HTTP 4xx - Show error message from response
- HTTP 5xx - Show generic "Server error, please try again"

---

## 📊 Application Sections (8-Step Wizard)

| Step | Section | Endpoint | Key Fields |
|------|---------|----------|------------|
| 1 | Category Selection | `/pre-applicant/select-tier` | category |
| 2 | Check Status | `/pre-applicant/check-status` | email |
| 3 | Payment | `/api/payments/initiate` | payment_type, user_type |
| 4 | Password Setup | `/access/generate-password` | email |
| 5 | Privacy Notice | `/privacy/accept` | email, accepted |
| 6 | Application Form | `/apply` | personal info, files |
| 7 | Review | N/A | Client-side only |
| 8 | Confirmation | N/A | Client-side only |

---

## 📋 Frontend State Management

```javascript
let userData = {
  fullName: '',              // From /pre-applicant/register
  email: '',                 // User's email
  category: '',              // 'regular' or 'vip'
  amount: 0,                 // In KOBO (518000 or 2590000)
  paymentReference: '',      // Paystack reference from /initiate
  preApplicantId: '',        // From /register
  applicantId: '',           // From /apply
  password: '',              // Generated or user-set
  applicationStatus: null,    // From /check-status
  savedProgress: null,       // From /get-progress
  isDraft: false             // Application in progress
};
```

---

## 🚫 Endpoints NOT Available

The following mentioned in frontend docs are **NOT** in the backend:

1. ~~`/apply` (POST)~~ → Use `/apply` with multipart form data
2. ~~`/save-progress`~~ → Use `/save-progress` POST
3. ~~`associate`, `full`, `corporate` tiers~~ → Only `regular` and `vip` exist

---

## 📅 Document Version

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-06-20 | Initial Backend API Documentation |
| 1.1 | 2026-06-20 | Added payment types, fixed tier names |

---

*This document was created by the Backend Agent. For questions, contact the backend team.*
