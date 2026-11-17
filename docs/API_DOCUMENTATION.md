# REST API Specification — NHT-SMS

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  
**API Version:** v1  
**Base URL:** `https://nht-sms.northernhighways.co.ke`  
**Data Format:** JSON (`application/json`)  
**Security Standard:** HTTPS Only, Strict Anti-IDOR, Idempotent Operations  

---

## 1. Authentication & Security Headers

NHT-SMS provides two primary authentication schemes:
1. **Session Authentication (Internal / Portal):** Standard Django session cookie (`sessionid`) accompanied by mandatory CSRF protection tokens (`X-CSRFToken`) for mutating requests (`POST`, `PUT`, `DELETE`).
2. **Bearer Token Authentication (External Webhooks):** External callbacks (such as Safaricom Daraja M-Pesa) provide a shared cryptographic token in the `Authorization` header:
   ```http
   Authorization: Bearer <MPESA_CALLBACK_TOKEN>
   ```

### Standard Response Envelope (Error)
```json
{
  "status": "error",
  "code": "PERMISSION_DENIED",
  "message": "Object-level authorization failed. You do not own this vehicle record.",
  "timestamp": "2026-11-17T22:00:00Z"
}
```

---

## 2. System Health & Infrastructure Endpoints

### 2.1 Liveness Probe
- **Endpoint:** `GET /health/live/`
- **Access:** Public (Bypasses rate limiting)
- **Purpose:** Verifies that the WSGI worker process is responsive.
- **Response:** `200 OK`
```json
{
  "status": "alive",
  "service": "NHT-SMS"
}
```

### 2.2 Readiness Probe
- **Endpoint:** `GET /health/ready/`
- **Access:** Public
- **Purpose:** Verifies active database connectivity (`SELECT 1;`).
- **Response:** `200 OK` (or `503 Service Unavailable` on DB failure)
```json
{
  "status": "ready",
  "database": "connected",
  "service": "NHT-SMS"
}
```

---

## 3. Public Regulatory Verification Endpoints

### 3.1 Public Vehicle QR Compliance Badge
- **Endpoint:** `GET /verify/vehicle/{qr_token}/`
- **Access:** Public (No authentication required)
- **Zero-PII Assurance:** Exposes only regulatory compliance state; strictly excludes member national ID, telephone, and private certificates.
- **Response:** `200 OK` (HTML badge) or JSON:
```json
{
  "vehicle": {
    "registration_number": "KAA 123B",
    "make_model": "Toyota HiAce (14-Seater)",
    "sacco_fleet_status": "ACTIVE"
  },
  "compliance": {
    "overall_status": "FULLY_COMPLIANT",
    "verified_at": "2026-11-17T22:00:00Z",
    "active_certificates": [
      {
        "category": "Inspection Certificate",
        "valid_until": "2027-05-15"
      },
      {
        "category": "Motor PSV Insurance",
        "valid_until": "2027-11-01"
      }
    ]
  }
}
```

---

## 4. Financial & Payment Webhook Endpoints

### 4.1 Safaricom Daraja M-Pesa Callback
- **Endpoint:** `POST /api/v1/payments/mpesa/callback/`
- **Access:** Safaricom Gateway (Protected via `MPESA_CALLBACK_TOKEN`)
- **Idempotency:** Re-delivered callbacks for previously recorded M-Pesa receipt numbers return HTTP 200 without creating duplicate ledger postings.
- **Request Body Example (STK Push Callback):**
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220261025537542",
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [
          {"Name": "Amount", "Value": 1500.00},
          {"Name": "MpesaReceiptNumber", "Value": "QAA12XYZ34"},
          {"Name": "TransactionDate", "Value": 20261117220000},
          {"Name": "PhoneNumber", "Value": 254712345678}
        ]
      }
    }
  }
}
```
- **Response:** `200 OK`
```json
{
  "ResultCode": 0,
  "ResultDesc": "Payment successfully allocated to invoice NHT-INV-2026-0042"
}
```

---

## 5. Member Portal Endpoints

| Method | Endpoint | Description | Anti-IDOR Gate |
|---|---|---|---|
| `GET` | `/portal/dashboard/` | Real-time member overview (fleet, unread alerts) | Member must own account |
| `GET` | `/portal/vehicles/` | Fleet listing for authenticated member | Filtered strictly to `request.member` |
| `GET` | `/portal/vehicles/{id}/` | Vehicle detail and compliance overview | `PermissionDenied` (403) if not owner |
| `GET` | `/portal/vehicles/{id}/card/` | Branded printable compliance card | `PermissionDenied` (403) if not owner |
| `GET` | `/portal/invoices/` | Chronological list of issued invoices | Filtered strictly to `request.member` |
| `GET` | `/portal/invoices/{id}/` | Invoice view with M-Pesa trigger | `PermissionDenied` (403) if not owner |
| `POST`| `/portal/invoices/{id}/pay/`| Initiates STK push to member phone | `PermissionDenied` (403) if not owner |
| `GET` | `/portal/renewals/` | History of document renewal requests | Filtered strictly to `request.member` |
| `POST`| `/portal/renewals/submit/` | Submits renewal request with replacement doc | Auto-attaches to `request.member` |
| `GET` | `/portal/statement/` | Chronological running financial ledger | Filtered strictly to `request.member` |
| `GET` | `/portal/receipts/{id}/` | Printable official SACCO receipt | `PermissionDenied` (403) if not owner |

---

## 6. Executive & Regulatory Reporting Endpoints

- **`GET /reports/dashboard/`**: Staff-only analytics (active fleet count, compliance %, monthly revenue, passenger load).
- **`GET /reports/export/compliance-pdf/`**: Generates high-resolution branded PDF audit report (`fpdf2`).
- **`GET /reports/export/financial-excel/`**: Generates multi-tab financial reconciliation workbook (`openpyxl`).
