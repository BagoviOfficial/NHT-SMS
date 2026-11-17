#!/usr/bin/env bash
# ==============================================================================
# NHT-SMS AUTOMATED DATABASE BACKUP SCRIPT
# Northern Highways Transporters SACCO Management System
# ==============================================================================

set -eo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups/db}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup target directory if not present
mkdir -p "${BACKUP_DIR}"

BACKUP_FILE="${BACKUP_DIR}/nht_sms_db_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

echo "=== [NHT-SMS Backup] Starting Database Backup at $(date) ==="
echo "Target: ${BACKUP_FILE}"

# Execute pg_dump
if [ -n "${DATABASE_URL}" ]; then
    pg_dump "${DATABASE_URL}" --clean --if-exists --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"
else
    DB_NAME="${POSTGRES_DB:-nht_sms_db}"
    DB_USER="${POSTGRES_USER:-$(whoami)}"
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"

    pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        --clean --if-exists --no-owner --no-privileges | gzip -9 > "${BACKUP_FILE}"
fi

# Verify backup was created and is non-empty
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup file ${BACKUP_FILE} is empty or was not created." >&2
    exit 1
fi

# Compute SHA-256 Cryptographic Checksum
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "=== [NHT-SMS Backup] Backup Complete ==="
echo "Size: ${BACKUP_SIZE}"
echo "Checksum file: ${CHECKSUM_FILE}"

# Prune backups older than retention window
echo "Pruning database backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -type f -name "nht_sms_db_*.sql.gz*" -mtime +"${RETENTION_DAYS}" -delete || true

echo "=== [NHT-SMS Backup] All operations finished successfully ==="
exit 0
