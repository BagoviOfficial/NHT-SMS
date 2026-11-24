import json
import logging
import re
import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Dict, List

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import (
    SystemConfiguration,
    ConfigurationHistory,
    ConfigurationChangeRequest,
    ChangeRequestStatus,
    ConfigCategory,
    ConfigDataType,
)
from .crypto import CryptoService
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Central database-backed, cached, typed configuration management service.
    Coordinates validation, credential encryption, caching, version history,
    safe rollback, and audit logging.
    """
    CACHE_PREFIX = "nht:config:"
    CACHE_TIMEOUT = 3600  # 1 hour cache TTL

    @classmethod
    def _cache_key(cls, key: str) -> str:
        return f"{cls.CACHE_PREFIX}{key}"

    @classmethod
    def _cast_value(cls, raw_value: str, data_type: str, is_secret: bool = False) -> Any:
        """
        Casts serialized string value to native Python type.
        """
        if is_secret:
            return CryptoService.decrypt(raw_value)
        
        if data_type == ConfigDataType.BOOLEAN:
            return str(raw_value).strip().lower() in ('true', '1', 'yes', 't', 'y')
        
        elif data_type == ConfigDataType.INTEGER:
            try:
                return int(raw_value.strip())
            except (ValueError, TypeError, AttributeError):
                return 0
        
        elif data_type == ConfigDataType.DECIMAL:
            try:
                return Decimal(str(raw_value).strip())
            except (InvalidOperation, TypeError):
                return Decimal('0.00')
        
        elif data_type == ConfigDataType.JSON:
            try:
                if isinstance(raw_value, (dict, list)):
                    return raw_value
                return json.loads(raw_value) if raw_value else {}
            except Exception:
                return {}
        
        elif data_type in (ConfigDataType.STRING, ConfigDataType.CHOICE):
            return str(raw_value) if raw_value is not None else ''
        
        elif data_type == ConfigDataType.ENCRYPTED_STRING:
            return CryptoService.decrypt(raw_value)
        
        return raw_value

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """
        Retrieves a typed configuration value.
        Checks cache first, then PostgreSQL, falling back to default or factory fallback.
        """
        cache_key = cls._cache_key(key)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            config = SystemConfiguration.objects.filter(key=key).first()
            if config:
                val = cls._cast_value(config.raw_value, config.data_type, config.is_secret)
                cache.set(cache_key, val, cls.CACHE_TIMEOUT)
                return val
        except Exception as e:
            logger.warning(f"Error querying SystemConfiguration for {key}: {str(e)}")

        return default

    @classmethod
    def get_str(cls, key: str, default: str = '') -> str:
        val = cls.get(key, default)
        return str(val) if val is not None else default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        val = cls.get(key, default)
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in ('true', '1', 'yes', 't', 'y')

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        val = cls.get(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_decimal(cls, key: str, default: Decimal = Decimal('0.00')) -> Decimal:
        val = cls.get(key, default)
        if isinstance(val, Decimal):
            return val
        try:
            return Decimal(str(val))
        except (InvalidOperation, TypeError):
            return default

    @classmethod
    def get_json(cls, key: str, default: Any = None) -> Any:
        val = cls.get(key, default)
        if val is not None:
            return val
        return default if default is not None else {}

    @classmethod
    def get_secret(cls, key: str, fallback: str = '') -> str:
        """
        Retrieves and decrypts a sensitive credential.
        Falls back to provided fallback (e.g. Django setting/env var) if missing or empty.
        """
        val = cls.get(key, None)
        if val:
            return str(val)
        return fallback

    @classmethod
    def invalidate_cache(cls, key: str):
        """Purges cached configuration value."""
        cache.delete(cls._cache_key(key))

    @classmethod
    def validate_value(cls, setting: SystemConfiguration, value: Any) -> str:
        """
        Validates user input against type constraints, choices, and regex patterns.
        Returns serialized raw string ready for database storage.
        """
        # If masked string submitted for secret, keep existing value
        if setting.is_secret and str(value).startswith('••••••••'):
            return setting.raw_value

        str_val = str(value).strip() if value is not None else ''

        # Choice validation
        if setting.data_type == ConfigDataType.CHOICE and setting.choices_json:
            if str_val not in setting.choices_json:
                raise ValidationError(f"Invalid choice '{str_val}'. Must be one of: {', '.join(setting.choices_json)}")

        # Regex validation
        if setting.validation_regex and str_val:
            if not re.match(setting.validation_regex, str_val):
                raise ValidationError(f"Value '{str_val}' does not match required format pattern.")

        # Data type validation
        if setting.data_type == ConfigDataType.INTEGER:
            try:
                int(str_val)
            except ValueError:
                raise ValidationError(f"Value '{str_val}' must be a valid integer.")

        elif setting.data_type == ConfigDataType.DECIMAL:
            try:
                Decimal(str_val)
            except InvalidOperation:
                raise ValidationError(f"Value '{str_val}' must be a valid decimal number.")

        elif setting.data_type == ConfigDataType.BOOLEAN:
            if str_val.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                raise ValidationError(f"Value '{str_val}' must be boolean (true/false).")
            str_val = 'true' if str_val.lower() in ('true', '1', 'yes') else 'false'

        elif setting.data_type == ConfigDataType.JSON:
            if isinstance(value, (dict, list)):
                str_val = json.dumps(value)
            else:
                try:
                    json.loads(str_val)
                except Exception as e:
                    raise ValidationError(f"Invalid JSON syntax: {str(e)}")

        # Encrypt secret if needed
        if setting.is_secret or setting.data_type == ConfigDataType.ENCRYPTED_STRING:
            str_val = CryptoService.encrypt(str_val)

        return str_val

    @classmethod
    def set(
        cls,
        key: str,
        value: Any,
        user=None,
        reason: str = '',
        ip_address: Optional[str] = None,
        expected_version: Optional[int] = None,
        confirm_critical: bool = True,
        enforce_approval: bool = False
    ) -> SystemConfiguration:
        """
        Persists a configuration mutation atomically.
        Enforces optimistic concurrency checks, dependency risk assessment,
        audit logging, version increments, and cache invalidation.
        """
        setting = SystemConfiguration.objects.filter(key=key).first()
        if not setting:
            raise ValidationError(f"Configuration key '{key}' does not exist in registry.")

        # 1. Optimistic locking / concurrency conflict detection
        if expected_version is not None and setting.version != expected_version:
            raise ValidationError(
                f"Concurrent modification conflict: setting '{key}' was modified by another administrator "
                f"(expected version {expected_version}, current version {setting.version}). Please refresh."
            )

        serialized_new = cls.validate_value(setting, value)
        serialized_old = setting.raw_value

        # If value hasn't changed, return without new version
        if serialized_new == serialized_old:
            return setting

        # 2. Dependency Risk Assessment and Critical Impact Guarding
        from .dependencies import ConfigurationDependencyRegistry
        impact = ConfigurationDependencyRegistry.assess_impact(key, value)
        if enforce_approval and impact.get('requires_approval') and not confirm_critical:
            warnings_text = " | ".join(impact.get('warnings', []))
            raise ValidationError(
                f"High-Risk Configuration Mutation Detected [{impact.get('risk_level')}]: "
                f"Modifying '{key}' impacts modules: {', '.join(impact.get('affected_modules', []))}. "
                f"Warnings: {warnings_text}. Explicit confirmation required (confirm_critical=True)."
            )

        with transaction.atomic():
            # Record audit history
            ConfigurationHistory.objects.create(
                setting=setting,
                version=setting.version,
                old_value=CryptoService.mask_secret(serialized_old) if setting.is_secret else serialized_old,
                new_value=CryptoService.mask_secret(serialized_new) if setting.is_secret else serialized_new,
                changed_by=user,
                changed_by_username=user.username if user else 'SYSTEM',
                ip_address=ip_address,
                reason=reason or f"Updated {setting.title}"
            )

            # Update configuration record
            setting.version += 1
            setting.raw_value = serialized_new
            setting.updated_by = user
            setting.save()

            # Record immutable security audit log
            AuditLog.log_action(
                actor=user,
                action=AuditAction.UPDATE,
                entity_type='SYSTEM_CONFIGURATION',
                entity_id=key,
                outcome=AuditOutcome.SUCCESS,
                notes=f"Configuration '{key}' updated to v{setting.version}. Reason: {reason or 'Administrative update'}",
                ip_address=ip_address,
                change_details={
                    'key': key,
                    'category': setting.category,
                    'version': setting.version,
                    'is_secret': setting.is_secret,
                    'risk_level': impact.get('risk_level', 'LOW'),
                }
            )

        # Invalidate cache
        cls.invalidate_cache(key)
        return setting

    @classmethod
    def rollback(
        cls,
        key: str,
        target_version: int,
        user=None,
        reason: str = '',
        ip_address: Optional[str] = None
    ) -> SystemConfiguration:
        """
        Rolls back configuration value to that of a previous version.
        """
        setting = SystemConfiguration.objects.filter(key=key).first()
        if not setting:
            raise ValidationError(f"Configuration key '{key}' does not exist.")

        hist = ConfigurationHistory.objects.filter(setting=setting, version=target_version).first()
        if not hist:
            # If target_version is 1 and no history exists, rollback to default_value
            if target_version == 1:
                target_value = setting.default_value
                if setting.is_secret:
                    target_value = CryptoService.encrypt(target_value)
            else:
                raise ValidationError(f"Historical version {target_version} not found for '{key}'.")
        else:
            # For secrets, if history was masked, we fetch from default or decrypt if stored encrypted
            target_value = hist.old_value
            if setting.is_secret and str(target_value).startswith('••••••••'):
                target_value = CryptoService.encrypt(setting.default_value)

        with transaction.atomic():
            ConfigurationHistory.objects.create(
                setting=setting,
                version=setting.version,
                old_value=CryptoService.mask_secret(setting.raw_value) if setting.is_secret else setting.raw_value,
                new_value=CryptoService.mask_secret(target_value) if setting.is_secret else target_value,
                changed_by=user,
                changed_by_username=user.username if user else 'SYSTEM',
                ip_address=ip_address,
                reason=reason or f"Rollback to v{target_version}"
            )

            setting.version += 1
            setting.raw_value = target_value
            setting.updated_by = user
            setting.save()

            AuditLog.log_action(
                actor=user,
                action=AuditAction.UPDATE,
                entity_type='SYSTEM_CONFIGURATION',
                entity_id=key,
                outcome=AuditOutcome.SUCCESS,
                notes=f"Configuration '{key}' rolled back to version {target_version} by {user.username if user else 'SYSTEM'}",
                ip_address=ip_address,
                change_details={'key': key, 'rolled_back_to_version': target_version}
            )

        cls.invalidate_cache(key)
        return setting

    @classmethod
    def export_configurations(cls, category: Optional[str] = None, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Exports configuration items into structured JSON format.
        Secrets are excluded by default for security. Includes SHA-256 integrity checksum.
        """
        qs = SystemConfiguration.objects.all()
        if category:
            qs = qs.filter(category=category)

        items = []
        for c in qs.order_by('category', 'key'):
            is_sec = c.is_secret
            val = "" if is_sec and not include_secrets else c.raw_value
            items.append({
                'key': c.key,
                'category': c.category,
                'data_type': c.data_type,
                'value': val,
                'is_secret': is_sec,
                'title': c.title,
                'version': c.version,
            })

        payload = {
            'system': 'NHT-SMS',
            'schema_version': '1.0',
            'exported_at': timezone.now().isoformat(),
            'item_count': len(items),
            'configurations': items,
        }

        # Calculate payload integrity checksum
        serialized = json.dumps(items, sort_keys=True)
        payload['sha256_checksum'] = hashlib.sha256(serialized.encode('utf-8')).hexdigest()
        return payload

    @classmethod
    def import_configurations(
        cls,
        payload: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
        verify_checksum: bool = False
    ) -> Dict[str, Any]:
        """
        Validates and imports configuration dictionary.
        Protects against invalid types, malicious inputs, or secret clobbering.
        When verify_checksum=True, enforces SHA-256 integrity verification.
        """
        if not isinstance(payload, dict):
            raise ValidationError("Import payload must be a valid JSON object.")

        if payload.get('system') != 'NHT-SMS':
            raise ValidationError("Invalid configuration payload: missing or incorrect system identifier.")

        items = payload.get('configurations', [])
        if not isinstance(items, list):
            raise ValidationError("Payload configurations attribute must be a list.")

        # Checksum integrity verification when requested
        if verify_checksum or payload.get('verify_checksum', False):
            expected_checksum = payload.get('sha256_checksum')
            if not expected_checksum:
                raise ValidationError("Integrity check failed: missing sha256_checksum in import payload.")
            serialized_check = json.dumps(items, sort_keys=True)
            computed_checksum = hashlib.sha256(serialized_check.encode('utf-8')).hexdigest()
            if computed_checksum != expected_checksum:
                raise ValidationError("Integrity check failed: configuration payload checksum mismatch. File may be corrupted or tampered with.")

        updated_count = 0
        skipped_count = 0

        with transaction.atomic():
            for item in items:
                key = item.get('key')
                if not key:
                    skipped_count += 1
                    continue

                setting = SystemConfiguration.objects.filter(key=key).first()
                if not setting:
                    skipped_count += 1
                    continue

                new_val = item.get('value')
                # If secret is blank or masked in import, skip to preserve existing secret
                if setting.is_secret and (not new_val or str(new_val).startswith('••••••••')):
                    skipped_count += 1
                    continue

                try:
                    cls.set(
                        key=key,
                        value=new_val,
                        user=user,
                        reason="Configuration batch import",
                        ip_address=ip_address,
                        confirm_critical=True
                    )
                    updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to import config key '{key}': {str(e)}")
                    skipped_count += 1

        return {
            'status': 'success',
            'updated': updated_count,
            'skipped': skipped_count,
            'timestamp': timezone.now().isoformat()
        }

    @classmethod
    @transaction.atomic
    def request_configuration_change(
        cls,
        key: str,
        proposed_value: Any,
        user,
        justification: str = '',
    ) -> ConfigurationChangeRequest:
        """
        Creates a Maker-Checker ConfigurationChangeRequest for sensitive settings.
        """
        setting = SystemConfiguration.objects.filter(key=key).first()
        if not setting:
            raise ValidationError(f"Configuration key '{key}' does not exist in registry.")

        serialized_new = cls.validate_value(setting, proposed_value)
        from .dependencies import ConfigurationDependencyRegistry
        impact = ConfigurationDependencyRegistry.assess_impact(key, proposed_value)

        cr = ConfigurationChangeRequest.objects.create(
            setting=setting,
            proposed_value=serialized_new,
            current_value=CryptoService.mask_secret(setting.raw_value) if setting.is_secret else setting.raw_value,
            status=ChangeRequestStatus.PENDING,
            risk_level=impact.get('risk_level', 'MEDIUM'),
            impact_assessment=impact,
            justification=justification or f"Change request for {setting.title}",
            requested_by=user,
        )
        AuditLog.log_action(
            actor=user,
            action=AuditAction.CREATE,
            entity_type='ConfigurationChangeRequest',
            entity_id=str(cr.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Requested config change for '{key}' (Risk: {cr.risk_level})",
        )
        return cr

    @classmethod
    @transaction.atomic
    def approve_configuration_change(
        cls,
        change_request: ConfigurationChangeRequest,
        reviewer,
        comments: str = '',
        ip_address: Optional[str] = None,
    ) -> ConfigurationChangeRequest:
        """
        Approves and applies a pending ConfigurationChangeRequest.
        Enforces strict Maker-Checker separation (reviewer != requested_by).
        """
        if change_request.status != ChangeRequestStatus.PENDING:
            raise ValidationError(f"Change request is already {change_request.status}.")
        if change_request.requested_by_id == getattr(reviewer, 'id', None):
            raise ValidationError("Maker-Checker violation: You cannot approve your own configuration change request.")

        setting = change_request.setting
        raw_val = change_request.proposed_value
        if setting.is_secret:
            raw_val = CryptoService.decrypt(raw_val)

        cls.set(
            key=setting.key,
            value=raw_val,
            user=reviewer,
            reason=f"Approved CR-{str(change_request.pk)[:8]}: {comments or change_request.justification}",
            ip_address=ip_address,
            confirm_critical=True,
            enforce_approval=False,
        )

        change_request.status = ChangeRequestStatus.APPROVED
        change_request.reviewed_by = reviewer
        change_request.review_comments = comments
        change_request.reviewed_at = timezone.now()
        change_request.applied_at = timezone.now()
        change_request.save(
            update_fields=['status', 'reviewed_by', 'review_comments', 'reviewed_at', 'applied_at']
        )

        AuditLog.log_action(
            actor=reviewer,
            action=AuditAction.APPROVE,
            entity_type='ConfigurationChangeRequest',
            entity_id=str(change_request.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Approved & applied change request for '{setting.key}'",
            ip_address=ip_address,
        )
        return change_request

    @classmethod
    @transaction.atomic
    def reject_configuration_change(
        cls,
        change_request: ConfigurationChangeRequest,
        reviewer,
        comments: str = '',
    ) -> ConfigurationChangeRequest:
        if change_request.status != ChangeRequestStatus.PENDING:
            raise ValidationError(f"Change request is already {change_request.status}.")
        if change_request.requested_by_id == getattr(reviewer, 'id', None):
            raise ValidationError("Maker-Checker violation: You cannot reject your own configuration change request.")

        change_request.status = ChangeRequestStatus.REJECTED
        change_request.reviewed_by = reviewer
        change_request.review_comments = comments
        change_request.reviewed_at = timezone.now()
        change_request.save(update_fields=['status', 'reviewed_by', 'review_comments', 'reviewed_at'])

        AuditLog.log_action(
            actor=reviewer,
            action=AuditAction.REJECT,
            entity_type='ConfigurationChangeRequest',
            entity_id=str(change_request.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Rejected change request for '{change_request.setting.key}': {comments}",
        )
        return change_request
