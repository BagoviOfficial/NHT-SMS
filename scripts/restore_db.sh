#!/usr/bin/env bash
# ==============================================================================
# NHT-SMS DATABASE RESTORATION UTILITY
# Northern Highways Transporters SACCO Management System
# ==============================================================================

set -eo pipefail

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_backup.sql.gz> [--force]"
    exit 1
fi

BACKUP_FILE="$1"
FORCE="$2"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: Backup archive '${BACKUP_FILE}' does not exist." >&2
    exit 1
fi

CHECKSUM_FILE="${BACKUP_FILE}.sha256"

# Verify Checksum if present
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "Verifying SHA-256 cryptographic integrity..."
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "${CHECKSUM_FILE}"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c "${CHECKSUM_FILE}"
    fi
    echo "Checksum verification successful."
else
    echo "WARNING: Checksum file ${CHECKSUM_FILE} not found. Proceeding without checksum check."
fi

# Confirmation gate
if [ "${FORCE}" != "--force" ]; then
    echo "================================================================="
    echo "WARNING: Restoring will overwrite existing data in the target DB!"
    echo "File: ${BACKUP_FILE}"
    echo "================================================================="
    read -r -p "Type 'RESTORE' to confirm database restoration: " CONFIRMATION
    if [ "${CONFIRMATION}" != "RESTORE" ]; then
        echo "Restoration aborted by operator."
        exit 1
    fi
fi

echo "=== [NHT-SMS Restore] Commencing database restoration at $(date) ==="

if [ -n "${DATABASE_URL}" ]; then
    gunzip -c "${BACKUP_FILE}" | psql "${DATABASE_URL}" --single-transaction
else
    DB_NAME="${POSTGRES_DB:-nht_sms_db}"
    DB_USER="${POSTGRES_USER:-$(whoami)}"
    DB_HOST="${POSTGRES_HOST:-localhost}"
    DB_PORT="${POSTGRES_PORT:-5432}"

    gunzip -c "${BACKUP_FILE}" | psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" --single-transaction
fi

echo "=== [NHT-SMS Restore] Database successfully restored from ${BACKUP_FILE} ==="
exit 0
