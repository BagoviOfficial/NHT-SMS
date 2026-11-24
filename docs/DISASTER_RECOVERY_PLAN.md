# Disaster Recovery Plan — NHT-SMS (Stage 13)

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  

---

## 1. Recovery Objectives

| Metric | Target | Notes |
|---|---|---|
| **RPO (Recovery Point Objective)** | 24 Hours (Daily automated `pg_dump` + media backups) | Increase cron frequency to hourly WAL/dump for higher transaction volume. |
| **RTO (Recovery Time Objective)** | < 1 Hour | Container rebuild + `scripts/restore_db.sh` + static/media sync. |

---

## 2. Step-by-Step Recovery Procedure

1. **Provision Database & Secrets:** Restore PostgreSQL, Redis, `.env` (`SECRET_KEY`, `DATABASE_URL`, `MPESA_CALLBACK_TOKEN`), and `SETTINGS_ENCRYPTION_KEY` (or `SETTINGS_ENCRYPTION_KEY_FILE`) from secure offline storage.
2. **Verify Checksum & Restore Database:**
   ```bash
   sha256sum -c backups/db/nht_sms_db_<timestamp>.sql.gz.sha256
   ./scripts/restore_db.sh backups/db/nht_sms_db_<timestamp>.sql.gz
   ```
3. **Restore Private Regulatory Document Vault:** Extract latest `backups/media/` archive into `media/private/` and verify SHA-256 checksums.
4. **Verify Key Integrity & Services:**
   ```bash
   python manage.py check --deploy
   python manage.py migrate --check
   ```
5. **Post-Recovery Validation:** Verify `/health/live/`, `/health/ready/`, `/app/`, and run `PaymentReconciliationService.run_reconciliation()` to detect any incomplete payment transactions during the outage window.
