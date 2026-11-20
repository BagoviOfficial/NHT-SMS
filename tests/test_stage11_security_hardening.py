import os
import tempfile
import json
import hashlib
from decimal import Decimal
import pytest

from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session

from django_otp.plugins.otp_totp.models import TOTPDevice

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.integrations.models import (
    SystemConfiguration,
    ConfigurationHistory,
    ConfigCategory,
    ConfigDataType,
)
from nht_sacco.apps.integrations.crypto import CryptoService
from nht_sacco.apps.integrations.services import ConfigurationService
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

User = get_user_model()


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_superuser(
        username="sec_superadmin",
        email="superadmin@northernhighways.co.ke",
        password="SuperSecureAdminPassword123!",
        role=UserRole.SUPER_ADMIN
    )


@pytest.fixture
def auditor_user(db):
    return User.objects.create_user(
        username="sec_auditor",
        email="auditor@northernhighways.co.ke",
        password="ValidAuditorPassword123!",
        role=UserRole.AUDITOR,
        is_staff=True
    )


@pytest.fixture
def member_user(db):
    return User.objects.create_user(
        username="sec_member",
        email="member@northernhighways.co.ke",
        password="ValidMemberPassword123!",
        role=UserRole.MEMBER
    )


# ==============================================================================
# 1. Key Management and Cryptographic Hardening Tests (11.2)
# ==============================================================================

@pytest.mark.django_db
class TestKeyManagementAndRotation:
    """Verifies production key independence, external file loading, and atomic key rotation."""

    def test_production_key_independence_enforced(self, monkeypatch):
        # Simulate non-testing, non-debug production runtime
        monkeypatch.setattr(settings, 'DEBUG', False)
        monkeypatch.setattr(settings, 'TESTING', False)
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY', None)
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY_FILE', None)

        with pytest.raises(ImproperlyConfigured) as exc:
            CryptoService.resolve_master_key()
        assert "SETTINGS_ENCRYPTION_KEY is required and must be independent" in str(exc.value)

    def test_production_key_identical_to_secret_key_rejected(self, monkeypatch):
        test_secret = 'django-insecure-test-secret-key-for-testing-purposes'
        monkeypatch.setattr(settings, 'DEBUG', False)
        monkeypatch.setattr(settings, 'TESTING', False)
        monkeypatch.setattr(settings, 'SECRET_KEY', test_secret)
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY', test_secret)
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY_FILE', None)

        with pytest.raises(ImproperlyConfigured) as exc:
            CryptoService.resolve_master_key()
        assert "SETTINGS_ENCRYPTION_KEY must not be identical to SECRET_KEY" in str(exc.value)

    def test_key_file_reading_supported(self, monkeypatch):
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write("external-file-encryption-key-for-containers-32chars")
            f_path = f.name

        try:
            monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY_FILE', f_path)
            key = CryptoService.resolve_master_key()
            assert key == "external-file-encryption-key-for-containers-32chars"
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_rotate_encryption_key_dry_run(self, superadmin_user):
        secret_item = SystemConfiguration.objects.filter(is_secret=True).first()
        if not secret_item:
            secret_item = SystemConfiguration.objects.create(
                key='test.secret_for_dryrun',
                category=ConfigCategory.SECURITY,
                data_type=ConfigDataType.ENCRYPTED_STRING,
                raw_value=CryptoService.encrypt('initial_secret_value'),
                is_secret=True,
                title='Test Secret'
            )
        initial_value = secret_item.raw_value

        # Execute dry-run via management command
        new_test_key = "a" * 32
        call_command('rotate_encryption_key', new_key=new_test_key, dry_run=True)

        # Confirm database value was not mutated
        secret_item.refresh_from_db()
        assert secret_item.raw_value == initial_value

    def test_rotate_all_secrets_with_fallback_migration(self, superadmin_user, monkeypatch):
        old_key = "old-cryptographic-master-key-32chars"
        new_key = "new-cryptographic-master-key-32chars"

        # Encrypt with old key
        token = CryptoService.encrypt("plaintext_secret_123", custom_key=old_key)
        assert CryptoService.decrypt(token, custom_key=old_key) == "plaintext_secret_123"

        # Rotate secrets
        re_encrypted = CryptoService.rotate_all_secrets(new_key=new_key, old_key=old_key, user=superadmin_user)
        assert re_encrypted >= 0

        # Verify fallback decryption when old key is in SETTINGS_ENCRYPTION_KEY_FALLBACKS
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY', new_key)
        monkeypatch.setattr(settings, 'SETTINGS_ENCRYPTION_KEY_FALLBACKS', [old_key])

        # Value encrypted with old key should still decrypt via MultiFernet fallback
        decrypted_fallback = CryptoService.decrypt(token)
        assert decrypted_fallback == "plaintext_secret_123"


# ==============================================================================
# 2. Configuration Security & Dependency Awareness Tests (11.3)
# ==============================================================================

@pytest.mark.django_db
class TestConfigurationSecurityAndDependencies:
    """Verifies dependency risk evaluation, critical mutation guarding, and optimistic concurrency."""

    def test_dependency_impact_assessment_api(self, client, superadmin_user):
        client.force_login(superadmin_user)
        resp = client.post(
            reverse('integrations:api_assess_impact'),
            data={'key': 'business.currency', 'proposed_value': 'USD'},
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['risk_level'] == 'CRITICAL'
        assert data['requires_approval'] is True
        assert 'accounting' in data['affected_modules']
        assert len(data['warnings']) > 0

    def test_critical_configuration_update_rejected_without_confirmation(self, client, superadmin_user):
        client.force_login(superadmin_user)
        # Attempt to update critical setting without confirm_critical
        resp = client.post(
            reverse('integrations:api_config_update'),
            data={'key': 'business.currency', 'value': 'USD', 'confirm_critical': False},
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert "High-Risk Configuration Mutation Detected" in resp.json()['error']

    def test_critical_configuration_update_succeeds_with_confirmation(self, client, superadmin_user):
        client.force_login(superadmin_user)
        # Explicitly confirm critical mutation
        resp = client.post(
            reverse('integrations:api_config_update'),
            data={'key': 'business.currency', 'value': 'USD', 'confirm_critical': True},
            content_type='application/json'
        )
        assert resp.status_code == 200
        assert ConfigurationService.get_str('business.currency') == 'USD'

    def test_optimistic_concurrency_conflict_detected(self, client, superadmin_user):
        client.force_login(superadmin_user)
        config = SystemConfiguration.objects.get(key='business.currency')

        # Send an update with an obsolete expected_version
        resp = client.post(
            reverse('integrations:api_config_update'),
            data={
                'key': 'business.currency',
                'value': 'KES',
                'expected_version': config.version + 999,
                'confirm_critical': True
            },
            content_type='application/json'
        )
        assert resp.status_code == 400
        assert "Concurrent modification conflict" in resp.json()['error']

    def test_import_payload_checksum_integrity_verification(self, superadmin_user):
        payload = ConfigurationService.export_configurations(include_secrets=False)

        # Tamper with the exported payload without updating checksum
        payload['configurations'][0]['value'] = 'TAMPERED_VALUE'

        with pytest.raises(ValidationError) as exc:
            ConfigurationService.import_configurations(
                payload,
                user=superadmin_user,
                verify_checksum=True
            )
        assert "Integrity check failed: configuration payload checksum mismatch" in str(exc.value)


# ==============================================================================
# 3. Authentication, MFA, Session Invalidation & Account Security Tests (11.4)
# ==============================================================================

@pytest.mark.django_db
class TestAuthenticationAndSessionHardening:
    """Verifies MFA enrollment, suspicious login detection, forced password change, and session termination."""

    def test_mfa_totp_setup_and_verification(self, client, superadmin_user):
        client.force_login(superadmin_user)

        # 1. Initiate setup
        setup_resp = client.get(reverse('accounts:totp_setup'))
        assert setup_resp.status_code == 200
        data = setup_resp.json()
        assert data['status'] == 'success'
        assert 'otpauth://totp/' in data['config_url']
        assert 'secret_key' in data

        device = TOTPDevice.objects.get(user=superadmin_user, confirmed=False)
        assert not device.confirmed

        # 2. Invalid token rejected
        bad_resp = client.post(reverse('accounts:totp_setup'), {'token': '000000'})
        assert bad_resp.status_code == 400
        assert "Invalid verification code" in bad_resp.json()['message']

        # 3. Valid token confirmation
        # Generate valid token using device oath TOTP engine
        import time
        from django_otp.oath import TOTP
        device.throttle_reset(commit=True)
        totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
        totp.time = time.time()
        token = str(totp.token()).zfill(device.digits)

        good_resp = client.post(reverse('accounts:totp_setup'), {'token': token})
        assert good_resp.status_code == 200
        device.refresh_from_db()
        assert device.confirmed is True

        # 4. Verify endpoint with next-step token (defends against token replay attack)
        totp.time = time.time() + device.step
        token2 = str(totp.token()).zfill(device.digits)
        verify_resp = client.post(reverse('accounts:totp_verify'), {'token': token2})
        assert verify_resp.status_code == 200
        assert verify_resp.json()['status'] == 'success'

    def test_suspicious_login_ip_mismatch_detected(self, client, superadmin_user):
        # Set prior login IP
        superadmin_user.last_login_ip = "192.168.1.100"
        superadmin_user.save(update_fields=['last_login_ip'])

        # Login from different IP address
        client.post(
            reverse('accounts:login'),
            {'username': 'sec_superadmin', 'password': 'SuperSecureAdminPassword123!'},
            REMOTE_ADDR="10.20.30.40"
        )

        # Check AuditLog for security alert
        assert AuditLog.objects.filter(
            actor=superadmin_user,
            entity_type='SECURITY_ALERT',
            change_details__alert_type='SUSPICIOUS_IP_CHANGE'
        ).exists()

    def test_forced_password_change_redirection(self, client, superadmin_user):
        superadmin_user.must_change_password = True
        superadmin_user.save(update_fields=['must_change_password'])

        client.force_login(superadmin_user)
        # Attempt to access dashboard
        resp = client.get(reverse('accounts:dashboard'))
        assert resp.status_code == 302
        assert resp.url == reverse('accounts:password_change')

        # Password change page is accessible
        pw_resp = client.get(reverse('accounts:password_change'))
        assert pw_resp.status_code == 200

    def test_session_invalidation_on_password_change(self, client, superadmin_user):
        client.force_login(superadmin_user)
        current_session_key = client.session.session_key

        # Create simulated secondary active session for same user
        from django.contrib.sessions.backends.db import SessionStore
        s2 = SessionStore()
        s2['_auth_user_id'] = str(superadmin_user.id)
        s2['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        s2.save()
        s2_key = s2.session_key
        assert Session.objects.filter(session_key=s2_key).exists()

        # Perform password change
        change_resp = client.post(
            reverse('accounts:password_change'),
            {
                'old_password': 'SuperSecureAdminPassword123!',
                'new_password1': 'NewEvenMoreSecurePassword456!',
                'new_password2': 'NewEvenMoreSecurePassword456!',
            }
        )
        assert change_resp.status_code == 302

        # Secondary session must be purged from database
        assert not Session.objects.filter(session_key=s2_key).exists()

        # Current session remains active
        superadmin_user.refresh_from_db()
        assert not superadmin_user.must_change_password

    def test_password_reset_anti_enumeration(self, client):
        # Request password reset for a non-existent email address
        resp = client.post(
            reverse('accounts:password_reset'),
            {'email': 'nonexistent_user@randomdomain.co.ke'}
        )
        # Must return 302 redirect to done page without disclosing non-existence
        assert resp.status_code == 302
        assert resp.url == reverse('accounts:password_reset_done')


# ==============================================================================
# 4. Role-Based Access Control (RBAC) Clearance Matrix Tests (11.4)
# ==============================================================================

@pytest.mark.django_db
class TestRBACAndPermissionsMatrix:
    """Verifies granular role authorization across SuperAdmin, Auditor, and Member."""

    def test_member_forbidden_from_admin_and_settings(self, client, member_user):
        client.force_login(member_user)

        # Settings index portal
        resp = client.get(reverse('integrations:settings_index'))
        assert resp.status_code == 403

        # Settings API
        resp_api = client.get(reverse('integrations:config_item-list'))
        assert resp_api.status_code == 403

        # Settings update API
        resp_update = client.post(
            reverse('integrations:api_config_update'),
            {'key': 'business.currency', 'value': 'USD'}
        )
        assert resp_update.status_code == 403

    def test_auditor_read_only_access_verified(self, client, auditor_user):
        client.force_login(auditor_user)

        # Auditor can inspect settings portal and APIs
        resp = client.get(reverse('integrations:settings_index'))
        assert resp.status_code == 200

        resp_api = client.get(reverse('integrations:config_item-list'))
        assert resp_api.status_code == 200

        # Auditor is strictly forbidden from mutating configurations
        resp_update = client.post(
            reverse('integrations:api_config_update'),
            {'key': 'business.currency', 'value': 'USD'}
        )
        assert resp_update.status_code == 403
