# NHT-SMS DYNAMIC SYSTEM CONFIGURATION & ADMINISTRATION FRAMEWORK GUIDE

**Document:** Enterprise System Configuration & Administration Manual  
**Classification:** Internal Restricted — Authorised System Administrators & Auditors  
**System Version:** Release v1.2.0 (Phase II — Sprint 2 / Stage 10)  
**Publication Date:** 2026-11-20  

---

## 1. Executive Summary & Objective

The **Dynamic System Configuration & Administration Framework** enables authorized administrators of the Northern Highways Transporters SACCO Management System (NHT-SMS) to configure payment gateways, notification providers, business operational rules, visual branding, and security access policies dynamically through an intuitive, role-gated web dashboard and secure REST APIs.

By transitioning all operational parameters to a PostgreSQL database-backed configuration registry with Redis caching:
- **Zero Source Code Edits**: Administrators can update production credentials, PayBill shortcodes, WhatsApp tokens, or loan interest rates without modifying codebase files.
- **Zero Downtime / Runtime Dynamism**: Gateway settings and business rules take effect immediately without requiring service restarts.
- **Cryptographic Security**: Sensitive credentials (consumer secrets, passkeys, API keys, passwords) are encrypted at rest using AES-256 (Fernet) and permanently masked in administration interfaces.
- **Auditability & Rollback**: Every mutation creates an immutable audit entry and a historical version snapshot, enabling safe one-click rollbacks.
- **Real-Time Diagnostics**: Built-in automated connectivity probes continuously monitor PostgreSQL, Redis, Celery workers, M-Pesa, SMS, WhatsApp, and SMTP relays.

---

## 2. Cryptographic Security & Secret Masking

All sensitive configuration parameters (`is_secret=True` or data type `ENCRYPTED_STRING`) are protected by a hardened cryptographic layer:

```
[Plaintext Credential] 
         │
         ▼
[CryptoService.encrypt()] ──(AES-256 Fernet via SETTINGS_ENCRYPTION_KEY)
         │
         ▼
[PostgreSQL Database: enc:gAAAAABn...] (Encrypted at rest)
         │
         ├──► [API & UI Display] ─────────► [CryptoService.mask_secret()] ──► "••••••••a1b2"
         └──► [Internal Service Adapters] ──► [CryptoService.decrypt()]     ──► Decrypted in memory only
```

### Encryption Key Management
1. The encryption key is derived using SHA-256 and URL-safe Base64 encoding from the environment variable `SETTINGS_ENCRYPTION_KEY`.
2. If `SETTINGS_ENCRYPTION_KEY` is not explicitly declared, the service safely falls back to `SECRET_KEY`.
3. In production, `SETTINGS_ENCRYPTION_KEY` should be set to a high-entropy 64-character secret managed by an external secrets manager or `.env`.

### Secret Masking Policy
- Plaintext credentials are **never** returned in GET API responses, web portal forms, audit logs, or export files.
- Masking format: `••••••••` + last 4 characters of the secret (or `••••••••` if length ≤ 4).
- In update forms, submitting a masked string (`••••••••...`) is recognized as "unchanged" and does not overwrite the existing secret.

---

## 3. Configuration Registry Architecture

The central service `nht_sacco.apps.integrations.services.ConfigurationService` manages all setting lookups with a two-tier caching pattern:

| Level | Storage | Latency | Invalidation Trigger |
|---|---|---|---|
| **L1 Cache** | Redis / Django Cache (`nht:config:<key>`) | < 1 ms | On setting update or rollback |
| **L2 Database** | PostgreSQL (`integrations_system_configuration`) | 1–3 ms | Authoritative source of truth |
| **Fallback** | `django.conf.settings` / `.env` defaults | In-memory | When record is missing from DB |

### Supported Data Types
- **`STRING`**: Text values (e.g. `business.sacco_name`).
- **`INTEGER`**: Whole numbers (e.g. `security.max_login_attempts`, `app.page_size`).
- **`DECIMAL`**: Exact financial numbers (e.g. `business.min_monthly_contribution`, `mpesa.max_amount`).
- **`BOOLEAN`**: True/False toggles (e.g. `app.module_vehicles_enabled`).
- **`JSON`**: Structured dictionaries and lists.
- **`CHOICE`**: Value constrained to an allowed list (e.g. `mpesa.environment` in `['sandbox', 'production']`).
- **`ENCRYPTED_STRING`**: AES-256 encrypted string (e.g. `mpesa.consumer_secret`).

---

## 4. Integration Management

### 4.1 Safaricom Daraja (M-Pesa)
Administrators can configure the following keys under the **External Integrations** tab:

| Setting Key | Description | Default | Secret |
|---|---|---|---|
| `mpesa.environment` | Target environment (`sandbox` or `production`) | `sandbox` | No |
| `mpesa.consumer_key` | Daraja OAuth Consumer Key | `sandbox_key` | **Yes** |
| `mpesa.consumer_secret` | Daraja OAuth Consumer Secret | `sandbox_secret` | **Yes** |
| `mpesa.business_shortcode` | PayBill / Till Number (e.g. 174379) | `174379` | No |
| `mpesa.passkey` | Lipa na M-Pesa Online passkey | `bfb2...` | **Yes** |
| `mpesa.transaction_type` | `CustomerPayBillOnline` or `CustomerBuyGoodsOnline` | `CustomerPayBillOnline` | No |
| `mpesa.callback_url` | Webhook URL for payment confirmations | `https://...` | No |
| `mpesa.callback_token` | Token verified in callback requests | `nht-...` | **Yes** |
| `mpesa.min_amount` | Minimum allowable payment (KES) | `1.00` | No |
| `mpesa.max_amount` | Maximum allowable payment ceiling (KES) | `150000.00` | No |
| `mpesa.timeout_seconds` | STK Push subscriber response timeout | `60` | No |

**Connectivity Testing**: Click the **Test** button next to M-Pesa Daraja on `/settings/` to trigger an immediate OAuth handshake against Safaricom and display real-time latency.

### 4.2 Africa's Talking SMS
| Setting Key | Description | Default | Secret |
|---|---|---|---|
| `sms.provider` | Provider adapter (`africastalking`, `twilio`, `sandbox`) | `africastalking` | No |
| `sms.username` | Account username | `sandbox` | No |
| `sms.api_key` | Secret API Key | `""` | **Yes** |
| `sms.sender_id` | Alphanumeric Sender ID | `NHT_SACCO` | No |
| `sms.environment` | `sandbox` or `production` | `sandbox` | No |

### 4.3 Meta WhatsApp Cloud API
| Setting Key | Description | Default | Secret |
|---|---|---|---|
| `whatsapp.provider` | Provider adapter (`meta_cloud`, `sandbox`) | `meta_cloud` | No |
| `whatsapp.api_token` | System User Permanent Token | `""` | **Yes** |
| `whatsapp.phone_number_id` | Phone Number ID from Meta Developer Console | `""` | No |
| `whatsapp.business_account_id` | WABA ID | `""` | No |
| `whatsapp.webhook_verify_token` | Webhook verification secret | `""` | **Yes** |

### 4.4 SMTP Email Relay
| Setting Key | Description | Default | Secret |
|---|---|---|---|
| `email.smtp_host` | Outgoing mail server host | `localhost` | No |
| `email.smtp_port` | Mail port (587, 465, 25) | `587` | No |
| `email.smtp_encryption` | `TLS`, `SSL`, or `NONE` | `TLS` | No |
| `email.smtp_username` | SMTP login username | `""` | No |
| `email.smtp_password` | SMTP login password | `""` | **Yes** |
| `email.sender_name` | Display name for emails | `Northern Highways...` | No |
| `email.sender_email` | Sender email address | `alerts@...` | No |

---

## 5. Business Configuration & Operations

Operational policies and corporate metadata are managed in the **Business Policies & Rules** tab:

- **Corporate Details**: Legal name (`business.sacco_name`), registration number (`business.registration_number`), tax PIN (`business.kra_pin`), physical address, and contact lines.
- **Document Prefixes**:
  - `business.invoice_prefix`: Default `NHT-INV` (e.g. `NHT-INV-2026-0001`).
  - `business.receipt_prefix`: Default `NHT-REC` (e.g. `NHT-REC-2026-0001`).
  - `business.voucher_prefix`: Default `NHT-VOU` (e.g. `NHT-VOU-2026-0001`).
- **Financial Rules**:
  - `business.min_monthly_contribution`: Minimum monthly subscription (KES 2,000.00).
  - `business.membership_entrance_fee`: Registration onboarding charge (KES 1,000.00).
  - `business.max_loan_multiplier`: Maximum borrowing ratio against savings (3.0x).
  - `business.default_interest_rate`: Standard reducing balance rate (12.0%).
  - `business.late_penalty_percent`: Overdue penalty rate (5.0%).
  - `business.receipt_footer_disclaimer`: Legal disclaimer printed on electronic receipts.

---

## 6. Application Customisation & Branding

Visual branding, regional formats, and module toggles are managed in the **Branding & Look** tab:

- **Application Title**: `app.name` and `app.short_name` dynamically update the navbar and browser tab titles.
- **Color Palettes**:
  - `app.brand_navy`: Primary navy color (e.g. `#10315C`).
  - `app.brand_blue`: Primary action blue (e.g. `#1B4A8A`).
  - `app.brand_orange`: Warning & accent orange (e.g. `#FF8A00`).
- **Localization**:
  - `app.date_format`: Presentation format (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`).
  - `app.timezone`: Standard timezone (`Africa/Nairobi`).
  - `app.page_size`: Records per table page (`25`).
- **Feature Module Toggles**:
  - `app.module_vehicles_enabled`: Commercial fleet management.
  - `app.module_compliance_enabled`: Document expiry and regulatory compliance.
  - `app.module_renewals_enabled`: Member self-service document renewals.
  - `app.module_governance_enabled`: AGMs, voting, and resolutions.
  - `app.module_maintenance_enabled`: Garage repair work orders.
  - `app.module_incidents_enabled`: Road traffic incident investigation.

---

## 7. Versioning, Audit Trail & Rollback

Every modification to any configuration parameter undergoes atomic versioning:

1. **Version Counter**: `version` increments by 1 on every change.
2. **History Capture**: `ConfigurationHistory` records the prior value, the new value (masked/encrypted if secret), the actor, their IP address, and their stated justification reason.
3. **Immutable Security Audit Log**: An `AuditLog` entry is written with `entity_type='SYSTEM_CONFIGURATION'` and `action='UPDATE'`.
4. **Safe Rollback**: In the **History & Rollback** tab, administrators can click **Rollback** on any historical record to restore that exact version.

---

## 8. Backup & Restoration

### Exporting Configurations
- In the **Backup & Restore** tab or via `GET /settings/export/`, administrators can download a JSON file.
- Sensitive credentials (`is_secret=True`) are **omitted** (value is `""`) to prevent accidental leaks.
- The payload includes system metadata, item count, and a SHA-256 integrity checksum.

### Importing Configurations
- Administrators upload a configuration JSON file via `POST /settings/import/`.
- The system verifies the system identifier (`NHT-SMS`), schema version, and data types.
- Missing or empty secret fields are automatically skipped, ensuring that existing production secrets are **never clobbered**.

---

## 9. Real-Time System Health Diagnostics

The **Health Diagnostics** tab provides active infrastructure probes:

| Service | Check Mechanism | Expected Status |
|---|---|---|
| **PostgreSQL** | `SELECT 1;` execution and latency measurement | `HEALTHY` (< 5 ms) |
| **Redis** | Ping/pong set-get validation | `HEALTHY` (< 2 ms) |
| **Celery** | Active worker heartbeat query via `celery.app.control.Inspect` | `HEALTHY` (Active nodes) |
| **M-Pesa Daraja** | Live OAuth token acquisition probe against Safaricom | `HEALTHY` (< 800 ms) |
| **Africa's Talking SMS** | API key verification & balance endpoint probe | `HEALTHY` |
| **Meta WhatsApp** | Graph API endpoint token inspection | `HEALTHY` |
| **SMTP Mail Relay** | TCP socket handshake to configured mail host & port | `HEALTHY` (< 50 ms) |

Diagnostics can be triggered on-demand via the web UI or programmatically via `/settings/api/v1/health/`.

---

## 10. Role-Based Access Control (RBAC) Matrix

| System Role | View Configurations | Modify Settings | Rollback Version | Export JSON | Import JSON | Test Probes |
|---|---|---|---|---|---|---|
| **SUPER_ADMIN** | Yes | Yes | Yes | Yes | Yes | Yes |
| **AUDITOR** | Yes (Read-Only) | Blocked (403) | Blocked (403) | Yes | Blocked (403) | Yes |
| **CHAIRMAN** | Yes (Read-Only) | Blocked (403) | Blocked (403) | Yes | Blocked (403) | Yes |
| **TREASURER / ACCOUNTANT** | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) |
| **COMPLIANCE / RENEWAL** | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) |
| **MEMBER / DRIVER** | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) | Blocked (403) |

---

## 11. REST API Endpoint Reference

| Endpoint | Method | Clearances | Description |
|---|---|---|---|
| `/settings/api/v1/configs/` | `GET` | SuperAdmin, Auditor | List all configuration items (secrets masked). |
| `/settings/api/v1/configs/<id>/` | `GET` | SuperAdmin, Auditor | Retrieve single configuration details. |
| `/settings/api/v1/update/` | `POST` | SuperAdmin | Update a configuration value atomically. |
| `/settings/api/v1/rollback/` | `POST` | SuperAdmin | Rollback setting to a specified target version. |
| `/settings/api/v1/export/` | `GET` | SuperAdmin, Auditor | Export non-secret configuration archive with checksum. |
| `/settings/api/v1/import/` | `POST` | SuperAdmin | Import configuration payload with validation. |
| `/settings/api/v1/health/` | `GET` | SuperAdmin, Auditor | Run real-time diagnostic health check suite. |
| `/settings/api/v1/test-provider/` | `POST` | SuperAdmin, Auditor | Execute connectivity probe for a single provider. |
