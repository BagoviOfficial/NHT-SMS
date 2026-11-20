# Changelog & Release Notes — NHT-SMS

All notable changes to the **Northern Highways Transporters SACCO Management System (NHT-SMS)** will be documented in this file.

The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v1.3.0] — 2026-11-20 (Phase II — Stage 11: Security Hardening & Independent Security Audit)

### Added
- **Production Cryptographic Key Independence (`apps/integrations/crypto.py`):** Strictly enforces independent `SETTINGS_ENCRYPTION_KEY` under production settings (`DEBUG=False`), preventing shared secret key vulnerability. Supports external key file loading via `SETTINGS_ENCRYPTION_KEY_FILE` for containerized environments.
- **Atomic Key Rotation Management Command (`management/commands/rotate_encryption_key.py`):** Production CLI tool supporting `--dry-run` simulation, `--key-file` external keys, atomic re-encryption of all stored secrets, and `SETTINGS_ENCRYPTION_KEY_FALLBACKS` for zero-downtime key migrations.
- **Configuration Dependency Awareness Framework (`apps/integrations/services.py`, `dependencies.py`):** Enforces impact assessment and mandatory confirmation (`confirm_critical=True`) before critical settings (`business.currency`, `mpesa.business_shortcode`, `mpesa.environment`) can be mutated. Added REST API endpoint `POST /settings/api/v1/assess-impact/`.
- **Optimistic Concurrency Locking (`apps/integrations/services.py`, `serializers.py`):** Detects concurrent modification race conditions across administrative updates via `expected_version` validation.
- **Cryptographic Checksum Verification on Imports (`apps/integrations/services.py`):** Verified SHA-256 payload checksum on configuration batch imports, preventing configuration payload tampering.
- **Multi-Factor Authentication (RFC 6238 TOTP) (`apps/accounts/views.py`, `urls.py`):** Implemented TOTP device enrollment (`/accounts/mfa/setup/`) with provisioning URI and backup hex tokens, challenge verification (`/accounts/mfa/verify/`), and anti-replay protection.
- **Conflict Resolution for `OTPMiddleware` (`apps/accounts/models.py`):** Implemented `User.save()` override safeguarding the model's `is_verified` boolean field from being overwritten by `OTPMiddleware` callable partial functions.
- **Session Security & Inactivity Timeout (`apps/accounts/middleware.py`):** `SessionSecurityMiddleware` enforcing 30-minute idle session timeout for management/administrative staff, and forced password change redirection when `must_change_password=True`.
- **Active Concurrent Session Invalidation (`apps/accounts/views.py`):** Automatically purges all other active sessions from `django.contrib.sessions` upon password change or reset.
- **Suspicious Login Detection (`apps/accounts/signals.py`):** Compares login IP against `user.last_login_ip` and emits high-priority `SECURITY_ALERT` audit logs on address changes.
- **Anti-User-Enumeration Password Reset (`apps/accounts/views.py`):** Generic, enumeration-resistant password reset request flow.
- **Stage 11 Security Test Suite (`tests/test_stage11_security_hardening.py`):** 17 new automated security tests (144 total tests across 11 stages passing with 100% success rate).
- **Formal Security Audit Reports (`docs/SECURITY_AUDIT_REPORT.md`, `docs/SECURITY_REMEDIATION_REPORT.md`):** Complete OWASP Top 10 / ASVS Level 2 source code audit, vulnerability classification matrix, and remediation evidence.

---

## [v1.2.0] — 2026-11-20 (Phase II — Sprint 2: Dynamic System Configuration & Administration Framework)

### Added
- **Dynamic Configuration Management Registry (`apps/integrations/models.py`):** PostgreSQL database-backed configuration registry (`SystemConfiguration`) supporting typed values (`STRING`, `INTEGER`, `DECIMAL`, `BOOLEAN`, `JSON`, `ENCRYPTED_STRING`, `CHOICE`), validation regex, and scope categorization.
- **Cryptographic Security Layer (`apps/integrations/crypto.py`):** AES-256 (Fernet) encryption at rest for sensitive credentials (`SETTINGS_ENCRYPTION_KEY`), automated secret masking (`••••••••ABCD`), and zero-leak protection in APIs and exports.
- **Central Configuration Service (`apps/integrations/services.py`):** High-performance `ConfigurationService` providing typed getters (`get_str`, `get_int`, `get_decimal`, `get_bool`, `get_secret`), Redis L1 caching with atomic invalidation, atomic transactions, version increments, and immutable security audit logs.
- **Immutable Version History & Rollback Engine (`apps/integrations/models.py`, `services.py`):** `ConfigurationHistory` tracking all configuration mutations, old/new masked values, actors, and IP addresses, with one-click version rollback.
- **Backup & Restoration Engine (`services.py`):** Non-secret JSON export with SHA-256 integrity checksum, schema validation, and safe import protecting existing secrets.
- **System Health Diagnostics Suite (`apps/integrations/diagnostics.py`):** Automated connectivity probes and latency telemetry for PostgreSQL, Redis, Celery workers, Safaricom Daraja, Africa's Talking SMS, Meta WhatsApp, and SMTP relays.
- **Administration Centre Web Portal (`templates/admin/settings/settings_index.html`):** Comprehensive Bootstrap 5 tabbed interface for Integrations, Business Policies, Application Look & Feel, Security, Health Diagnostics, History, and Backup/Restore.
- **Programmatic REST APIs (`apps/integrations/views.py`, `urls.py`):** Full suite of DRF endpoints under `/settings/api/v1/` for configuration retrieval, atomic updates, version rollback, export, import, and diagnostic testing.
- **Fine-Grained RBAC Controls (`apps/integrations/permissions.py`):** SuperAdmin full access, Auditor read-only inspection, and strict HTTP 403 Forbidden rejection for regular members and drivers.
- **Dynamic Adapter Refactoring:** Upgraded `DarajaClient`, `AfricasTalkingSMSAdapter`, `MetaWhatsAppAdapter`, `EmailNotificationAdapter`, `brand_context`, and invoice/receipt numbering generators to resolve values dynamically without service restarts.
- **Database Migrations (`0001_initial.py`, `0002_seed_default_configurations.py`):** Created tables and seeded 64 initial default configuration items across all 5 operational categories.
- **Comprehensive Stage 10 Test Suite (`tests/test_stage10_configuration_management.py`):** 22 new automated unit and integration tests (127 total tests across 10 stages passing with 100% success rate).
- **Enterprise Administrator Documentation (`docs/CONFIGURATION_AND_SETTINGS_GUIDE.md`):** Authoritative 16th production guide detailing configuration, security, integration setup, rollback, and diagnostics.

---

## [v1.1.0] — 2026-11-20 (Phase II — Sprint 1: Payment Security & Financial Integrity)

### Added
- **Genuine Daraja OAuth v1 Authentication (`apps/payments/daraja.py`):** Client credentials flow (`/oauth/v1/generate?grant_type=client_credentials`) with automatic in-memory access token caching and expiration buffer.
- **Genuine STK Push Dispatch & Status Query (`apps/payments/daraja.py`):** Live outbound API integration (`/mpesa/stkpush/v1/processrequest`) with zero simulated responses in production. Added transaction status query (`/mpesa/stkpushquery/v1/query`).
- **Token-Based Webhook Authentication (`apps/payments/views.py`):** Enforces callback origin validation via query parameter (`?token=...`), header (`X-Callback-Token`), or Bearer token; rejects unauthenticated webhooks with HTTP 401 and security audit logging.
- **Callback Financial Validation (`apps/payments/daraja.py`):** Strict verification of CheckoutRequestID, payment amount consistency, normalized telephone number matching, and initial payment state validation prior to transaction settlement.
- **Centralised Financial Posting Engine (`apps/accounting/services.py`):** `AccountingService.record_payment_settlement()` coordinating row-level locking (`select_for_update()`), payment confirmation, invoice balance allocation, official receipt generation, double-entry general ledger posting (Dr Cash/M-Pesa, Cr Accounts Receivable), and audit logging within a single atomic transaction.
- **Database Migration (`0002_alter_journalentry_posted_by.py`):** Allowed nullable `posted_by` on `JournalEntry` for automated gateway postings while preserving foreign key integrity.
- **Invoice Balance Property (`apps/billing/models.py`):** Added `@property def is_fully_paid` resolving template crashes and preventing duplicate STK initiation on settled invoices.
- **Production Startup Secret Validation (`config/settings/production.py`):** `validate_production_secrets()` enforcing presence of strong `SECRET_KEY`, valid `DATABASE_URL`, live Daraja credentials, and cryptographic callback tokens before booting in production.
- **Harmonized Environment Variables:** Unified naming for Daraja, Africa's Talking (`AT_USERNAME`, `AT_API_KEY`, `AT_SENDER_ID`), Meta WhatsApp Cloud API, and simulation flags across settings and environment templates.
- **Extended Automated Test Suite:** Expanded test suite from 89 to 105 tests across Stage 4, Stage 8, and Stage 9 covering payment security, concurrency, duplicate journals, and failure scenarios.

---

## [v1.0.0-rc1] — 2026-11-17 (Stage 9: Production Readiness & Release Package)

### Added
- **Multi-Container Docker Architecture:** Fully orchestrated `docker-compose.yml` defining isolated `web`, `db`, `redis`, `celery_worker`, `celery_beat`, and `nginx` services.
- **Production Containerization:** Hardened multi-stage `Dockerfile` running as non-root user `appuser` (UID 10001) with built-in health checks.
- **Nginx Reverse Proxy Configurations:** Dual configurations for container stack (`docker/nginx/nht_sacco.conf`) and native Ubuntu VPS (`docker/nginx/nht_sacco_vps.conf`) featuring TLS 1.2/1.3, HSTS, security headers, rate-limiting, and static caching.
- **Systemd Service Units:** Native Linux daemon configurations for Gunicorn, Celery Worker, and Celery Beat.
- **Automated Backup & Disaster Recovery Automation:** Production shell scripts (`scripts/backup_db.sh`, `scripts/restore_db.sh`, `scripts/backup_media.sh`) featuring SHA-256 cryptographic checksum generation and 30-day retention pruning.
- **Celery Asynchronous Tasks & Automation:** Configured Celery application (`nht_sacco/config/celery.py`) and periodic schedules for daily compliance scans, overdue invoice reminders, notification retries, and monthly member statements.
- **CLI Management Commands:** Added `python manage.py run_compliance_scan` and `python manage.py send_invoice_reminders`.
- **Database Migration Synchronization:** Generated and applied `0002_alter_document_file.py` in `documents` app, verifying zero pending model changes.
- **Complete 15 Production Guides:** Authored exhaustive enterprise documentation in `docs/` and root.
- **Automated Test Suite:** Created `tests/test_stage9_production_readiness.py` expanding test coverage to 85+ total passing tests.

---

## [v0.8.0] — 2026-11-17 (Stage 8: Security Hardening & ASVS Verification)

### Added
- **Binary Signature & Magic-Byte Validation (`apps/documents/validators.py`):** Rigid file header inspection enforcing `%PDF`, `\xff\xd8\xff`, and `\x89PNG\r\n\x1a\n` signatures to block disguised executable scripts.
- **Anti-IDOR Object Authorization:** Explicit ownership checks preventing cross-tenant manipulation across vehicles, invoices, receipts, and digital member cards.
- **Cryptographic & Financial Immutability:** Model-level validation blocking update and deletion mutations on `AuditLog` and posted `JournalEntry`.
- **Zero-PII Public QR Verification:** Public vehicle QR badge page concealing member national IDs, phone numbers, and private documents.
- **Security Test Suite:** 13 specialized dynamic penetration and immutability tests (`tests/test_stage8_security.py`).

---

## [v0.7.0] — 2026-11-17 (Stage 7: SACCO Operations & Governance)

### Added
- **Vehicle Maintenance Engine (`apps/maintenance`):** Service provider directory, spare parts usage tracking, sequential work orders (`NHT-MNT-YYYY-XXXX`), and fleet downtime computation.
- **Incident & Grievance Investigation (`apps/incidents`):** End-to-end incident resolution workflow (`SUBMITTED` -> `UNDER_INVESTIGATION` -> `RESOLVED`), investigator assignment, and corrective action logging.
- **Board & Committee Governance (`apps/governance`):** Committee rosters, formal meeting agendas (`NHT-MTG-YYYY-XXXX`), and resolution voting records (`NHT-RES-YYYY-XXXX`).
- **Executive Analytics & Reporting (`apps/reports`):** Real-time KPI metrics dashboard, high-resolution branded compliance PDF report generator (`fpdf2`), and multi-tab financial Excel reconciliation exporter (`openpyxl`).

---

## [v0.6.0] — 2026-11-17 (Stage 6: Communications & Member Self-Service Portal)

### Added
- **Multi-Channel Notification Dispatcher (`apps/notifications`):** Decoupled adapters for Africa's Talking (SMS), Meta WhatsApp Cloud API, SMTP Email, and In-App notification center.
- **Member Communication Preferences:** Granular opt-in/opt-out toggles and category suppressions.
- **Member Self-Service Portal (`/portal/`):** Hardened dashboard, fleet view, printable digital vehicle compliance cards, self-service vehicle registration requests, and document renewal submissions.
- **Running Financial Statement:** Real-time chronological timeline tracking debits, credits, and running balance.

---

## [v0.5.0] — 2026-11-17 (Stage 5: Accounting & Document Renewals)

### Added
- **Double-Entry General Ledger (`apps/accounting`):** Standard 5-tier Chart of Accounts, dynamic balance computation, balanced journal assertions ($\sum \text{Dr} = \sum \text{Cr}$), and financial period locking.
- **Reversal Journal Engine:** Reversal-only correction mechanism for posted journal entries.
- **Document Renewal State Machine (`apps/renewals`):** Structured renewal lifecycle from submission to invoice generation, payment settlement, and automatic compliance badge updates.
- **Expense Maker-Checker:** Dual-authorization controls for operating expense disbursements.

---

## [v0.4.0] — 2026-11-17 (Stage 4: Billing & Daraja Payment Processing)

### Added
- **Service Catalogue & Pricing (`apps/billing`):** Configurable pricing with effective date windows; strict separation of SACCO revenue from statutory fees.
- **Invoicing Engine:** Unique sequential invoice generation (`NHT-INV-YYYY-XXXX`) using strict Decimal arithmetic.
- **Safaricom Daraja M-Pesa Gateway (`apps/payments`):** STK Push (Lipa na M-Pesa Online) and C2B payment callbacks with strict idempotency and row-level locking (`select_for_update()`).
- **Official Sequential Receipting:** Branded printable receipts (`NHT-REC-YYYY-XXXX`).
- **Manual Payment Controls:** Maker-checker workflow for physical bank deposit slip verification.

---

## [v0.3.0] — 2026-11-17 (Stage 3: Compliance & Regulatory Document Vault)

### Added
- **Private Document Vault (`apps/documents`):** Storage isolation outside web root (`media/private/`) with SHA-256 checksum tracking.
- **Compliance Rules Engine (`apps/compliance`):** Automated regulatory evaluation comparing active certificates against mandatory requirements.
- **Automated Expiry Alerts:** Expiry scanning generating alerts at `[30, 14, 7, 3, 0]` day thresholds.
- **Tamper-Resistant QR Engine:** Zero-PII public verification tokens linked to registered vehicles.

---

## [v0.2.0] — 2026-11-17 (Stage 2: Membership & Fleet Management)

### Added
- **Membership Management (`apps/members`):** Multi-stage membership approval and suspension workflows.
- **Commercial Fleet Registry (`apps/vehicles`):** Vehicle registration, chassis/engine tracking, and multi-ownership percentage allocation (verifying 100% total sum).
- **Driver & Route Allocations (`apps/drivers`, `apps/routes`):** Driver PSV endorsements, vehicle crew assignments, route scheduling, and stage directory.

---

## [v0.1.0] — 2026-11-17 (Stage 1: Foundation & Core Architecture)

### Added
- **Core Architecture:** Custom UUID User model, RBAC role flags, settings structure (`base`, `development`, `testing`, `production`).
- **Tamper-Evident Audit Logging (`apps/audit`):** Automated request middleware and model-level immutability enforcement.
- **Health Check Probes:** Liveness probe (`/health/live/`) and readiness database connectivity probe (`/health/ready/`).
- **Authentication Security:** `django-axes` brute-force lockout, `django-otp` TOTP MFA, and secure session management.
