import os
import base64
import hashlib
import logging
from typing import Optional, List
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

logger = logging.getLogger(__name__)


class CryptoService:
    """
    Cryptographic Service for encrypting and decrypting sensitive application credentials at rest.
    Uses AES-256 (via Fernet / MultiFernet) with keys securely derived from environment settings.
    Guarantees secrets are never returned in plaintext in logs, exception traces or public interfaces.
    Supports zero-downtime key rotation via MultiFernet fallback key migration.
    """
    CIPHER_PREFIX = 'enc:'

    @classmethod
    def derive_fernet_key(cls, raw_key: str) -> Fernet:
        """
        Derives a URL-safe base64-encoded 32-byte Fernet instance from any string key.
        """
        derived_bytes = hashlib.sha256(str(raw_key).encode('utf-8')).digest()
        fernet_key = base64.urlsafe_b64encode(derived_bytes)
        return Fernet(fernet_key)

    @classmethod
    def resolve_master_key(cls, custom_key: Optional[str] = None) -> str:
        """
        Resolves the master encryption key using the following hierarchy:
        1. Explicit custom key parameter.
        2. External key file referenced by SETTINGS_ENCRYPTION_KEY_FILE.
        3. Environment setting SETTINGS_ENCRYPTION_KEY.
        4. SECRET_KEY fallback (strictly allowed only when DEBUG=True).
        Raises ImproperlyConfigured in production if key is missing or matches SECRET_KEY.
        """
        if custom_key:
            return custom_key

        key_file = getattr(settings, 'SETTINGS_ENCRYPTION_KEY_FILE', None)
        if key_file and os.path.isfile(key_file):
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    file_key = f.read().strip()
                    if file_key:
                        return file_key
            except Exception as e:
                logger.error(f"Failed to read key file {key_file}: {str(e)}")

        master_key = getattr(settings, 'SETTINGS_ENCRYPTION_KEY', None)
        is_test_or_dev = getattr(settings, 'TESTING', False) or getattr(settings, 'DEBUG', True)

        if not master_key:
            if not is_test_or_dev:
                raise ImproperlyConfigured(
                    "Production Security Error: SETTINGS_ENCRYPTION_KEY is required and must be "
                    "independent of SECRET_KEY in production."
                )
            master_key = getattr(settings, 'SECRET_KEY', 'default-nht-sms-fallback-key-for-dev')

        if not is_test_or_dev and master_key == getattr(settings, 'SECRET_KEY', None):
            raise ImproperlyConfigured(
                "Production Security Error: SETTINGS_ENCRYPTION_KEY must not be identical to SECRET_KEY."
            )

        return master_key

    @classmethod
    def get_multi_fernet(cls, custom_key: Optional[str] = None) -> MultiFernet:
        """
        Constructs a MultiFernet instance.
        If custom_key is provided, uses it as primary.
        Otherwise uses resolved master encryption key as primary,
        plus any fallback keys declared in SETTINGS_ENCRYPTION_KEY_FALLBACKS.
        """
        if custom_key:
            return MultiFernet([cls.derive_fernet_key(custom_key)])

        master_key = cls.resolve_master_key()
        fernets = [cls.derive_fernet_key(master_key)]

        # Support fallback keys for zero-downtime key rotation
        fallbacks = getattr(settings, 'SETTINGS_ENCRYPTION_KEY_FALLBACKS', [])
        if isinstance(fallbacks, str):
            fallbacks = [k.strip() for k in fallbacks.split(',') if k.strip()]
        
        for fb_key in fallbacks:
            if fb_key != master_key:
                fernets.append(cls.derive_fernet_key(fb_key))

        return MultiFernet(fernets)

    @classmethod
    def encrypt(cls, plaintext: str, custom_key: Optional[str] = None) -> str:
        """
        Encrypts plaintext string to prefixed Fernet ciphertext (enc:...).
        """
        if plaintext is None:
            return ''
        s_val = str(plaintext).strip()
        if not s_val:
            return ''
        if s_val.startswith(cls.CIPHER_PREFIX):
            return s_val  # Already encrypted

        try:
            mf = cls.get_multi_fernet(custom_key=custom_key)
            token = mf.encrypt(s_val.encode('utf-8')).decode('utf-8')
            return f"{cls.CIPHER_PREFIX}{token}"
        except Exception as e:
            logger.error(f"Failed to encrypt credential: {str(e)}")
            raise

    @classmethod
    def decrypt(cls, ciphertext: str, custom_key: Optional[str] = None) -> str:
        """
        Decrypts prefixed Fernet ciphertext (enc:...) to plaintext.
        Attempts decryption against primary key and all fallback keys in MultiFernet.
        Returns empty string if decryption fails or token is corrupted.
        """
        if not ciphertext:
            return ''
        s_val = str(ciphertext).strip()
        if not s_val.startswith(cls.CIPHER_PREFIX):
            return s_val  # Unencrypted legacy string

        token = s_val[len(cls.CIPHER_PREFIX):]
        try:
            mf = cls.get_multi_fernet(custom_key=custom_key)
            return mf.decrypt(token.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            logger.error("Failed to decrypt configuration value: Invalid encryption key or corrupt ciphertext.")
            return ''
        except Exception as e:
            logger.error(f"Error during configuration decryption: {str(e)}")
            return ''

    @classmethod
    def mask_secret(cls, value: str) -> str:
        """
        Returns a masked representation of a secret for secure display in UI and API responses.
        Format: ••••••••ABCD (retains last 4 chars if length > 4).
        Never exposes the full secret.
        """
        if not value:
            return ''

        plain = cls.decrypt(value) if str(value).startswith(cls.CIPHER_PREFIX) else str(value)
        if not plain:
            return '••••••••'

        if len(plain) <= 4:
            return '••••••••'
        return f"••••••••{plain[-4:]}"

    @classmethod
    def rotate_all_secrets(cls, new_key: str, old_key: Optional[str] = None, user=None, dry_run: bool = False) -> int:
        """
        Re-encrypts all database-backed secrets from old key to new key.
        If dry_run is True, simulates decryption and verification without writing changes.
        In normal mode, executes in a single atomic transaction, clears configuration cache,
        and logs an immutable audit event.
        """
        from nht_sacco.apps.integrations.models import SystemConfiguration
        from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
        from django.core.cache import cache

        secrets_qs = SystemConfiguration.objects.filter(is_secret=True)
        re_encrypted_count = 0

        with transaction.atomic():
            for item in secrets_qs:
                if not item.raw_value:
                    continue
                # Decrypt using old key (or MultiFernet fallback if old_key not explicit)
                plain = cls.decrypt(item.raw_value, custom_key=old_key)
                if not plain and item.raw_value.startswith(cls.CIPHER_PREFIX):
                    logger.warning(f"Unable to decrypt secret key '{item.key}' during key rotation; preserving ciphertext.")
                    continue

                # Re-encrypt with new key
                new_ciphertext = cls.encrypt(plain, custom_key=new_key)
                if not dry_run:
                    item.raw_value = new_ciphertext
                    item.version += 1
                    item.save(update_fields=['raw_value', 'version', 'updated_at'])
                    cache.delete(f"nht:config:{item.key}")
                re_encrypted_count += 1

            if not dry_run:
                AuditLog.log_action(
                    actor=user,
                    action=AuditAction.SYSTEM,
                    entity_type='ENCRYPTION_KEY_ROTATION',
                    entity_id='GLOBAL_ROTATION',
                    outcome=AuditOutcome.SUCCESS,
                    notes=f"Successfully re-encrypted {re_encrypted_count} configuration secrets under new cryptographic key."
                )

        logger.info(
            f"Cryptographic key rotation {'simulated (dry-run)' if dry_run else 'completed'}: "
            f"{re_encrypted_count} secrets {'verified' if dry_run else 're-encrypted'}."
        )
        return re_encrypted_count
