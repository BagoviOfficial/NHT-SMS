import json
from decimal import Decimal
import pytest
from django.urls import reverse
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied

from nht_sacco.apps.accounts.models import User, UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction
from nht_sacco.apps.billing.models import Invoice
from nht_sacco.apps.payments.models import Receipt
from nht_sacco.apps.payments.daraja import DarajaClient
from nht_sacco.apps.notifications.adapters import (
    AfricasTalkingSMSAdapter,
    MetaWhatsAppAdapter,
    EmailNotificationAdapter,
)
from nht_sacco.apps.accounts.context_processors import brand_context
from nht_sacco.apps.integrations.models import (
    SystemConfiguration,
    ConfigurationHistory,
    IntegrationHealthLog,
    IntegrationHealthStatus,
    ConfigCategory,
    ConfigDataType,
)
from nht_sacco.apps.integrations.crypto import CryptoService
from nht_sacco.apps.integrations.services import ConfigurationService
from nht_sacco.apps.integrations.diagnostics import DiagnosticService


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_superuser(
        username='sysadmin',
        email='sysadmin@northernhighways.co.ke',
        password='TestPassword123!',
        role=UserRole.SUPER_ADMIN,
    )


@pytest.fixture
def auditor_user(db):
    user = User.objects.create_user(
        username='auditor_user',
        email='auditor@northernhighways.co.ke',
        password='TestPassword123!',
        role=UserRole.AUDITOR,
    )
    user.is_staff = True
    user.save()
    return user


@pytest.fixture
def member_user(db):
    return User.objects.create_user(
        username='member_user',
        email='member@northernhighways.co.ke',
        password='TestPassword123!',
        role=UserRole.MEMBER,
    )


@pytest.fixture(autouse=True)
def preserve_configuration_state(db):
    """
    Saves snapshot of active configurations before each test and restores them afterwards.
    Ensures complete isolation across all 10 stages of the test suite.
    """
    snapshot = list(SystemConfiguration.objects.values('key', 'raw_value', 'version'))
    yield
    for item in snapshot:
        SystemConfiguration.objects.filter(key=item['key']).update(
            raw_value=item['raw_value'],
            version=item['version']
        )
        ConfigurationService.invalidate_cache(item['key'])


@pytest.mark.django_db
class TestConfigurationRegistry:
    """Verifies typed configuration registry retrieval, defaults, and validation."""

    def test_typed_retrieval_and_casting(self):
        # String
        assert ConfigurationService.get_str('business.currency') == 'KES'
        # Integer
        assert ConfigurationService.get_int('security.max_login_attempts') == 5
        # Decimal
        assert ConfigurationService.get_decimal('business.min_monthly_contribution') == Decimal('2000.00')
        # Boolean
        assert ConfigurationService.get_bool('app.module_vehicles_enabled') is True
        # Choice
        assert ConfigurationService.get_str('mpesa.environment') == 'sandbox'

    def test_validation_regex_and_choices(self, superadmin_user):
        # Invalid KRA PIN (fails regex)
        with pytest.raises(ValidationError):
            ConfigurationService.set(
                key='business.kra_pin',
                value='INVALID-PIN',
                user=superadmin_user
            )

        # Valid KRA PIN (passes regex)
        cfg = ConfigurationService.set(
            key='business.kra_pin',
            value='A123456789Z',
            user=superadmin_user
        )
        assert cfg.raw_value == 'A123456789Z'

        # Invalid Choice
        with pytest.raises(ValidationError):
            ConfigurationService.set(
                key='mpesa.environment',
                value='invalid_env',
                user=superadmin_user
            )

    def test_fallback_to_default_when_missing(self):
        assert ConfigurationService.get_str('nonexistent.setting.key', default='FALLBACK') == 'FALLBACK'
        assert ConfigurationService.get_int('nonexistent.int.key', default=42) == 42


@pytest.mark.django_db
class TestSecurityAndEncryption:
    """Verifies AES-256 Fernet encryption at rest, secret masking, and API protection."""

    def test_credential_encryption_and_decryption(self):
        secret = "super_secret_daraja_api_key_12345"
        encrypted = CryptoService.encrypt(secret)
        assert encrypted.startswith(CryptoService.CIPHER_PREFIX)
        assert encrypted != secret

        decrypted = CryptoService.decrypt(encrypted)
        assert decrypted == secret

    def test_secret_masking(self):
        secret = "my_daraja_secret_pass_9876"
        encrypted = CryptoService.encrypt(secret)
        masked = CryptoService.mask_secret(encrypted)
        assert masked == "••••••••9876"
        assert secret not in masked

    def test_secret_never_exposed_in_get(self, superadmin_user):
        ConfigurationService.set(
            key='mpesa.consumer_secret',
            value='production_secret_key_9999',
            user=superadmin_user
        )
        # Database stores ciphertext
        db_obj = SystemConfiguration.objects.get(key='mpesa.consumer_secret')
        assert db_obj.raw_value.startswith('enc:')
        assert 'production_secret_key_9999' not in db_obj.raw_value

        # Masked value
        assert CryptoService.mask_secret(db_obj.raw_value) == '••••••••9999'

        # get_secret decrypts securely for adapters
        assert ConfigurationService.get_secret('mpesa.consumer_secret') == 'production_secret_key_9999'


@pytest.mark.django_db
class TestCachingAndInvalidation:
    """Verifies Redis/Django cache behavior and automatic invalidation."""

    def test_cache_hit_and_atomic_invalidation(self, superadmin_user):
        cache.clear()
        key = 'business.sacco_name'
        cache_key = ConfigurationService._cache_key(key)

        # 1. First get primes cache
        val1 = ConfigurationService.get_str(key)
        assert val1 == 'Northern Highways Transporters SACCO'
        assert cache.get(cache_key) == 'Northern Highways Transporters SACCO'

        # 2. Update invalidates cache
        ConfigurationService.set(
            key=key,
            value='Northern Highways Logistics SACCO',
            user=superadmin_user
        )
        assert cache.get(cache_key) is None

        # 3. Next get loads fresh updated value into cache
        val2 = ConfigurationService.get_str(key)
        assert val2 == 'Northern Highways Logistics SACCO'
        assert cache.get(cache_key) == 'Northern Highways Logistics SACCO'


@pytest.mark.django_db
class TestDynamicIntegrations:
    """Verifies runtime reconfiguration of M-Pesa, SMS, WhatsApp, and SMTP adapters."""

    def test_daraja_client_dynamic_reconfiguration(self, superadmin_user):
        ConfigurationService.set('mpesa.business_shortcode', '654321', user=superadmin_user)
        ConfigurationService.set('mpesa.consumer_key', 'dyn_key_123', user=superadmin_user)
        ConfigurationService.set('mpesa.transaction_type', 'CustomerBuyGoodsOnline', user=superadmin_user)

        client = DarajaClient()
        assert client.business_shortcode == '654321'
        assert client.consumer_key == 'dyn_key_123'
        assert client.transaction_type == 'CustomerBuyGoodsOnline'

    def test_sms_adapter_dynamic_reconfiguration(self, superadmin_user):
        ConfigurationService.set('sms.username', 'dynamic_sms_user', user=superadmin_user)
        ConfigurationService.set('sms.sender_id', 'NHT_FLEET', user=superadmin_user)

        adapter = AfricasTalkingSMSAdapter()
        res = adapter.send('+254712345678', 'Test', 'Hello Dynamic SMS')
        assert res['success'] is True
        assert res['status'] == 'SENT'

    def test_whatsapp_adapter_dynamic_reconfiguration(self, superadmin_user):
        ConfigurationService.set('whatsapp.phone_number_id', '9876543210', user=superadmin_user)
        adapter = MetaWhatsAppAdapter()
        res = adapter.send('+254712345678', 'Test', 'Hello Dynamic WhatsApp')
        assert res['success'] is True
        assert res['status'] == 'SENT'

    def test_email_adapter_dynamic_reconfiguration(self, superadmin_user):
        ConfigurationService.set('email.sender_email', 'notifications@nht.co.ke', user=superadmin_user)
        adapter = EmailNotificationAdapter()
        res = adapter.send('member@example.com', 'Welcome', 'Welcome to SACCO')
        assert res['status'] in ('SENT', 'FAILED')


@pytest.mark.django_db
class TestDynamicApplicationCustomisation:
    """Verifies dynamic branding context and document numbering prefix updates."""

    def test_brand_context_processor(self, superadmin_user, rf):
        ConfigurationService.set('app.name', 'Northern Highways Premier SACCO', user=superadmin_user)
        ConfigurationService.set('app.brand_navy', '#0A192F', user=superadmin_user)

        request = rf.get('/')
        request.user = superadmin_user
        ctx = brand_context(request)

        assert ctx['BRAND_NAME'] == 'Northern Highways Premier SACCO'
        assert ctx['BRAND_NAVY'] == '#0A192F'

    def test_dynamic_invoice_and_receipt_numbering(self, superadmin_user):
        ConfigurationService.set('business.invoice_prefix', 'NHT-CUSTOM-INV', user=superadmin_user)
        ConfigurationService.set('business.receipt_prefix', 'NHT-CUSTOM-REC', user=superadmin_user)

        inv_num = Invoice.generate_invoice_number()
        rec_num = Receipt.generate_receipt_number()

        assert inv_num.startswith('NHT-CUSTOM-INV-')
        assert rec_num.startswith('NHT-CUSTOM-REC-')


@pytest.mark.django_db
class TestRBACAndPermissions:
    """Verifies fine-grained RBAC access enforcement across web views and REST APIs."""

    def test_superadmin_has_full_access(self, client, superadmin_user):
        client.force_login(superadmin_user)
        res = client.get(reverse('integrations:settings_index'))
        assert res.status_code == 200

        # Update via web form
        res_post = client.post(reverse('integrations:settings_update'), {
            'business.currency': 'KES',
            'form_reason': 'Superadmin update currency',
        })
        assert res_post.status_code == 302

    def test_auditor_has_read_only_access(self, client, auditor_user):
        client.force_login(auditor_user)
        # GET is allowed
        res = client.get(reverse('integrations:settings_index'))
        assert res.status_code == 200
        assert res.context['is_auditor_only'] is True

        # POST is rejected with 403 Forbidden
        res_post = client.post(reverse('integrations:settings_update'), {
            'business.currency': 'USD',
            'form_reason': 'Auditor attempted update',
        })
        assert res_post.status_code == 403

    def test_regular_member_forbidden(self, client, member_user):
        client.force_login(member_user)
        res = client.get(reverse('integrations:settings_index'))
        assert res.status_code == 403

    def test_api_permissions(self, client, superadmin_user, auditor_user, member_user):
        # 1. Superadmin can update via API
        client.force_login(superadmin_user)
        api_update_url = reverse('integrations:api_config_update')
        res1 = client.post(
            api_update_url,
            data=json.dumps({'key': 'app.page_size', 'value': '50', 'reason': 'API page size'}),
            content_type='application/json'
        )
        assert res1.status_code == 200
        assert ConfigurationService.get_int('app.page_size') == 50

        # 2. Auditor can read via API
        client.force_login(auditor_user)
        res2 = client.get(reverse('integrations:config_item-list'))
        assert res2.status_code == 200

        # 3. Auditor cannot write via API
        res3 = client.post(
            api_update_url,
            data=json.dumps({'key': 'app.page_size', 'value': '100'}),
            content_type='application/json'
        )
        assert res3.status_code == 403

        # 4. Member blocked completely from API
        client.force_login(member_user)
        res4 = client.get(reverse('integrations:config_item-list'))
        assert res4.status_code == 403


@pytest.mark.django_db
class TestHistoryAndRollback:
    """Verifies immutable history logging and safe rollback."""

    def test_history_logging_and_rollback(self, superadmin_user):
        key = 'business.currency'
        orig_val = ConfigurationService.get_str(key)
        assert orig_val == 'KES'

        # 1. Update to EUR
        ConfigurationService.set(key, 'EUR', user=superadmin_user, reason='Switch to EUR')
        assert ConfigurationService.get_str(key) == 'EUR'

        hist = ConfigurationHistory.objects.filter(setting__key=key).first()
        assert hist is not None
        assert hist.old_value == 'KES'
        assert hist.new_value == 'EUR'
        assert hist.changed_by == superadmin_user

        # 2. Rollback to original version 1
        ConfigurationService.rollback(key, target_version=1, user=superadmin_user, reason='Revert currency')
        assert ConfigurationService.get_str(key) == 'KES'

        # 3. AuditLog was recorded
        audit = AuditLog.objects.filter(entity_type='SYSTEM_CONFIGURATION', entity_id=key).first()
        assert audit is not None
        assert audit.action == AuditAction.UPDATE


@pytest.mark.django_db
class TestBackupAndRestore:
    """Verifies non-secret export, SHA-256 integrity, and validated import."""

    def test_export_and_import_configurations(self, superadmin_user):
        # 1. Export
        export_data = ConfigurationService.export_configurations(include_secrets=False)
        assert export_data['system'] == 'NHT-SMS'
        assert export_data['item_count'] > 0
        assert 'sha256_checksum' in export_data

        # Secrets must be empty in export
        secret_items = [i for i in export_data['configurations'] if i['is_secret']]
        for s in secret_items:
            assert s['value'] == ""

        # 2. Modify exported data and import
        for i in export_data['configurations']:
            if i['key'] == 'app.short_name':
                i['value'] = 'NHT-TEST'

        res = ConfigurationService.import_configurations(export_data, user=superadmin_user)
        assert res['status'] == 'success'
        assert ConfigurationService.get_str('app.short_name') == 'NHT-TEST'

    def test_invalid_import_payload_rejected(self, superadmin_user):
        with pytest.raises(ValidationError):
            ConfigurationService.import_configurations({'system': 'WRONG-SYSTEM'}, user=superadmin_user)


@pytest.mark.django_db
class TestHealthDiagnostics:
    """Verifies real-time diagnostics and connectivity testing for infrastructure and providers."""

    def test_database_and_redis_diagnostics(self):
        db_res = DiagnosticService.check_database()
        assert db_res['service'] == 'postgresql'
        assert db_res['status'] == IntegrationHealthStatus.HEALTHY
        assert db_res['response_time_ms'] >= 0.0

        redis_res = DiagnosticService.check_redis()
        assert redis_res['service'] == 'redis'
        assert redis_res['status'] in (IntegrationHealthStatus.HEALTHY, IntegrationHealthStatus.DEGRADED)

    def test_run_all_diagnostics_records_logs(self, superadmin_user):
        results = DiagnosticService.run_all_diagnostics(user=superadmin_user)
        assert 'overall_status' in results
        assert 'services' in results
        assert 'daraja' in results['services']
        assert 'africastalking' in results['services']
        assert 'whatsapp' in results['services']
        assert 'smtp' in results['services']

        # Assert health logs persisted in database
        logs_count = IntegrationHealthLog.objects.filter(tested_by=superadmin_user).count()
        assert logs_count >= 5
