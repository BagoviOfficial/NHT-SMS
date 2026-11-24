# Operations, Backup & Disaster Recovery Guide — NHT-SMS (Stage 13)

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  

---

## 1. Routine Operations & Background Jobs

- **Daily Compliance Scan:** `python manage.py run_compliance_scan` (or Celery `task_daily_compliance_scan`) evaluates all active vehicles using `timezone.localdate()` (`Africa/Nairobi`) and emits `ComplianceAlert` records for `[30, 14, 7, 3, 0]`-day thresholds and expired/missing mandatory documents.
- **Overdue Invoice Reminders:** `python manage.py send_invoice_reminders` (or Celery `task_overdue_invoice_reminders`) notifies members with unpaid invoices past `due_date`.
- **Payment Reconciliation:** Triggered from the SPA (`/app/#reconciliation`) or `PaymentReconciliationService.run_reconciliation()`.
- **System Diagnostics:** Available at `/settings/api/v1/health/` and in the SPA Administration Settings view, probing PostgreSQL, Redis, Celery, Daraja, Africa's Talking, Meta WhatsApp, and SMTP.

---

## 2. Backup & Restoration Procedures

- **Database Backup:** `scripts/backup_db.sh` executes `pg_dump` compressed to `.sql.gz` with a `.sha256` integrity checksum in `backups/db/`.
- **Media Vault Backup:** `scripts/backup_media.sh` archives private regulatory documents and calculates SHA-256 verification digests.
- **Restoration:** `scripts/restore_db.sh <archive.sql.gz>` verifies the `.sha256` digest prior to restoring into PostgreSQL.
- **Encryption Key Availability:** Ensure `SETTINGS_ENCRYPTION_KEY` (or `SETTINGS_ENCRYPTION_KEY_FILE`) is backed up separately in a secure secret store; encrypted configuration secrets in `SystemConfiguration` require the matching Fernet key (or `SETTINGS_ENCRYPTION_KEY_FALLBACKS` during key rotation).
