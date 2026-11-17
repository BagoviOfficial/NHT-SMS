# Changelog & Release Notes — NHT-SMS

All notable changes to the **Northern Highways Transporters SACCO Management System (NHT-SMS)** will be documented in this file.

The project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
