#!/usr/bin/env bash
# ==============================================================================
# NHT-SMS MEDIA & DOCUMENT VAULT BACKUP SCRIPT
# Northern Highways Transporters SACCO Management System
# ==============================================================================

set -eo pipefail

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="${BACKUP_DIR:-$(pwd)/backups/media}"
MEDIA_DIR="${MEDIA_DIR:-$(pwd)/media}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

mkdir -p "${BACKUP_DIR}"

BACKUP_FILE="${BACKUP_DIR}/nht_sms_media_${TIMESTAMP}.tar.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

echo "=== [NHT-SMS Media Backup] Starting Media Vault Backup at $(date) ==="
echo "Source: ${MEDIA_DIR}"
echo "Target: ${BACKUP_FILE}"

if [ ! -d "${MEDIA_DIR}" ]; then
    echo "ERROR: Media directory '${MEDIA_DIR}' does not exist." >&2
    exit 1
fi

# Create tar.gz archive
tar -czf "${BACKUP_FILE}" -C "$(dirname "${MEDIA_DIR}")" "$(basename "${MEDIA_DIR}")"

# Verify non-empty
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "ERROR: Media backup file is empty." >&2
    exit 1
fi

# Compute SHA-256 Checksum
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "=== [NHT-SMS Media Backup] Media Archive Created ==="
echo "Size: ${BACKUP_SIZE}"
echo "Checksum file: ${CHECKSUM_FILE}"

# Prune old media archives
find "${BACKUP_DIR}" -type f -name "nht_sms_media_*.tar.gz*" -mtime +"${RETENTION_DAYS}" -delete || true

echo "=== [NHT-SMS Media Backup] Finished successfully ==="
exit 0
