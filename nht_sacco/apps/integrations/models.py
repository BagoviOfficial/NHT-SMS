import hashlib
import os
import time
import uuid
from django.core.files.base import ContentFile
from django.db import IntegrityError, OperationalError, connection, models, transaction
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .validators import validate_company_logo


class ConfigCategory(models.TextChoices):
    INTEGRATIONS = 'INTEGRATIONS', _('External Integrations')
    BUSINESS = 'BUSINESS', _('Business & Operations')
    APPLICATION = 'APPLICATION', _('Application Customisation')
    SECURITY = 'SECURITY', _('Security Policies')
    SYSTEM = 'SYSTEM', _('System & Runtime')


class ConfigDataType(models.TextChoices):
    STRING = 'STRING', _('Text / String')
    INTEGER = 'INTEGER', _('Integer')
    DECIMAL = 'DECIMAL', _('Decimal Number')
    BOOLEAN = 'BOOLEAN', _('Boolean (True/False)')
    JSON = 'JSON', _('Structured JSON')
    ENCRYPTED_STRING = 'ENCRYPTED_STRING', _('Encrypted Secret')
    CHOICE = 'CHOICE', _('Choice Selection')


class SystemConfiguration(models.Model):
    """
    Central database-backed configuration registry item.
    Supports typed values, scopes, categories, default values,
    validation rules, and encryption for sensitive credentials.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(
        _('Configuration Key'),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Unique dot-notated key e.g. mpesa.consumer_key, business.sacco_name')
    )
    category = models.CharField(
        _('Category'),
        max_length=30,
        choices=ConfigCategory.choices,
        default=ConfigCategory.SYSTEM,
        db_index=True
    )
    data_type = models.CharField(
        _('Data Type'),
        max_length=30,
        choices=ConfigDataType.choices,
        default=ConfigDataType.STRING
    )
    raw_value = models.TextField(
        _('Stored Value'),
        blank=True,
        default='',
        help_text=_('Serialized or ciphertext representation of the active value')
    )
    default_value = models.TextField(
        _('Default Value'),
        blank=True,
        default='',
        help_text=_('Fallback factory default')
    )
    is_secret = models.BooleanField(
        _('Is Secret / Sensitive'),
        default=False,
        help_text=_('If true, value is encrypted at rest and masked in UI/API responses')
    )
    is_system_locked = models.BooleanField(
        _('System Locked'),
        default=False,
        help_text=_('System-locked keys cannot be deleted via admin interface')
    )
    requires_restart = models.BooleanField(
        _('Requires Service Restart'),
        default=False,
        help_text=_('Indicates whether this change requires worker or service restart')
    )
    requires_approval = models.BooleanField(
        _('Requires Maker-Checker Approval'),
        default=False,
        help_text=_('Requires explicit administrative approval to activate')
    )
    title = models.CharField(
        _('Setting Title'),
        max_length=150,
        help_text=_('Human-readable display name')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Detailed explanation and usage instructions')
    )
    validation_regex = models.CharField(
        _('Validation Regex'),
        max_length=255,
        blank=True,
        help_text=_('Optional regex pattern for validating user input')
    )
    choices_json = models.JSONField(
        _('Allowed Choices'),
        default=list,
        blank=True,
        help_text=_('List of allowed choice values for CHOICE data type')
    )
    version = models.PositiveIntegerField(
        _('Version Number'),
        default=1,
        help_text=_('Monotonically increasing version counter')
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_configurations',
        verbose_name=_('Last Updated By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations_system_configuration'
        verbose_name = _('System Configuration')
        verbose_name_plural = _('System Configurations')
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category', 'key']),
            models.Index(fields=['is_secret']),
        ]

    def __str__(self):
        return f"{self.key} ({self.get_category_display()}) - v{self.version}"


class ConfigurationHistory(models.Model):
    """
    Immutable audit history of all configuration mutations, supporting safe rollback.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    setting = models.ForeignKey(
        SystemConfiguration,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_('Configuration Setting')
    )
    version = models.PositiveIntegerField(_('Version'))
    old_value = models.TextField(
        _('Old Value'),
        blank=True,
        help_text=_('Old serialized value or masked/encrypted representation')
    )
    new_value = models.TextField(
        _('New Value'),
        blank=True,
        help_text=_('New serialized value or masked/encrypted representation')
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuration_mutations',
        verbose_name=_('Changed By')
    )
    changed_by_username = models.CharField(_('Username'), max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    reason = models.TextField(_('Change Reason / Justification'), blank=True)
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'integrations_configuration_history'
        verbose_name = _('Configuration History Entry')
        verbose_name_plural = _('Configuration History Entries')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['setting', 'version']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.setting.key} v{self.version} by {self.changed_by_username or 'SYSTEM'} at {self.timestamp}"


class IntegrationHealthStatus(models.TextChoices):
    HEALTHY = 'HEALTHY', _('Healthy / Operational')
    DEGRADED = 'DEGRADED', _('Degraded Performance')
    DOWN = 'DOWN', _('Down / Unreachable')
    UNCONFIGURED = 'UNCONFIGURED', _('Unconfigured / Incomplete')


class IntegrationHealthLog(models.Model):
    """
    Diagnostic log recording real-time and scheduled connectivity and health checks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_name = models.CharField(
        _('Service / Provider Name'),
        max_length=50,
        db_index=True,
        help_text=_('e.g. daraja, africastalking, whatsapp, smtp, postgresql, redis, celery')
    )
    status = models.CharField(
        _('Health Status'),
        max_length=20,
        choices=IntegrationHealthStatus.choices,
        default=IntegrationHealthStatus.HEALTHY,
        db_index=True
    )
    response_time_ms = models.FloatField(
        _('Response Time (ms)'),
        default=0.0
    )
    details = models.JSONField(
        _('Diagnostic Details'),
        default=dict,
        blank=True
    )
    error_message = models.TextField(
        _('Error Message'),
        blank=True
    )
    tested_at = models.DateTimeField(
        _('Tested At'),
        auto_now_add=True,
        db_index=True
    )
    tested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diagnostic_probes',
        verbose_name=_('Tested By')
    )

    class Meta:
        db_table = 'integrations_health_log'
        verbose_name = _('Integration Health Log')
        verbose_name_plural = _('Integration Health Logs')
        ordering = ['-tested_at']
        indexes = [
            models.Index(fields=['service_name', 'status']),
            models.Index(fields=['tested_at']),
        ]

    def __str__(self):
        return f"{self.service_name}: {self.status} ({self.response_time_ms:.1f}ms) at {self.tested_at}"


class ChangeRequestStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Checker Approval')
    APPROVED = 'APPROVED', _('Approved & Applied')
    REJECTED = 'REJECTED', _('Rejected')
    CANCELLED = 'CANCELLED', _('Cancelled by Requester')


class ConfigurationChangeRequest(models.Model):
    """
    Maker-Checker approval entity for critical and high-risk configuration changes.
    Enforces strict segregation of duties (Checker != Maker).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    setting = models.ForeignKey(
        SystemConfiguration,
        on_delete=models.CASCADE,
        related_name='change_requests',
        verbose_name=_('Target Setting')
    )
    proposed_value = models.TextField(
        _('Proposed Value'),
        help_text=_('Serialized or ciphertext representation of proposed change')
    )
    current_value = models.TextField(
        _('Current Value Snapshot'),
        blank=True,
        help_text=_('Snapshot of active value at the time the change was requested')
    )
    status = models.CharField(
        _('Approval Status'),
        max_length=20,
        choices=ChangeRequestStatus.choices,
        default=ChangeRequestStatus.PENDING,
        db_index=True
    )
    risk_level = models.CharField(
        _('Assessed Risk Level'),
        max_length=20,
        default='MEDIUM',
        db_index=True
    )
    impact_assessment = models.JSONField(
        _('Impact Assessment Metadata'),
        default=dict,
        blank=True
    )
    justification = models.TextField(
        _('Business Justification / Reason'),
        blank=True
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='configuration_requests_made',
        verbose_name=_('Requested By (Maker)')
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='configuration_requests_reviewed',
        verbose_name=_('Reviewed By (Checker)')
    )
    review_comments = models.TextField(
        _('Review Comments'),
        blank=True
    )
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'integrations_change_request'
        verbose_name = _('Configuration Change Request')
        verbose_name_plural = _('Configuration Change Requests')
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'risk_level']),
            models.Index(fields=['requested_at']),
        ]

    def __str__(self):
        return f"CR-{str(self.id)[:8]}: {self.setting.key} [{self.status}] by {self.requested_by.username}"


class NumberSequence(models.Model):
    """
    Concurrency-safe atomic sequence generator for business identifiers
    (membership numbers, invoices, receipts, payments, journals, compliance cards).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prefix = models.CharField(_('Prefix'), max_length=50)
    year = models.PositiveIntegerField(_('Year'), default=0)
    last_number = models.PositiveIntegerField(_('Last Allocated Sequence'), default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations_number_sequence'
        verbose_name = _('Number Sequence')
        verbose_name_plural = _('Number Sequences')
        constraints = [
            models.UniqueConstraint(fields=['prefix', 'year'], name='uniq_number_sequence_prefix_year'),
        ]

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.last_number}"

    @classmethod
    def _seed_max_from_model(cls, prefix, target_year, model_cls, field_name):
        if model_cls is None or not field_name:
            return 0
        stem = f"{prefix}-{target_year}-" if target_year else f"{prefix}-"
        existing = model_cls.objects.filter(**{f"{field_name}__startswith": stem}).values_list(field_name, flat=True)
        max_num = 0
        for val in existing:
            if not val:
                continue
            try:
                suffix = int(str(val).rsplit('-', 1)[-1])
                if suffix > max_num:
                    max_num = suffix
            except (ValueError, TypeError):
                continue
        return max_num

    @classmethod
    def next_number(cls, prefix, year=None, model_cls=None, field_name=None, width=4):
        target_year = int(year) if year is not None else timezone.now().year
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with transaction.atomic():
                    seq = cls.objects.select_for_update().filter(prefix=prefix, year=target_year).first()
                    if seq is None:
                        seed_val = cls._seed_max_from_model(prefix, target_year, model_cls, field_name)
                        try:
                            with transaction.atomic():
                                seq = cls.objects.create(
                                    prefix=prefix,
                                    year=target_year,
                                    last_number=seed_val,
                                )
                        except IntegrityError:
                            pass
                        seq = cls.objects.select_for_update().get(prefix=prefix, year=target_year)
                    seq.last_number += 1
                    seq.save(update_fields=['last_number', 'updated_at'])
                    if target_year:
                        return f"{prefix}-{target_year}-{seq.last_number:0{width}d}"
                    return f"{prefix}-{seq.last_number:0{width}d}"
            except OperationalError:
                if connection.vendor == 'sqlite' and attempt < max_attempts - 1:
                    time.sleep(0.02 * (attempt + 1))
                    continue
                raise


def branding_logo_upload_path(instance, filename):
    _, ext = os.path.splitext(filename or '')
    safe_ext = ext.lower() if ext.lower() in ('.png', '.jpg', '.jpeg') else '.png'
    return f"branding/logos/{uuid.uuid4()}{safe_ext}"


def branding_history_upload_path(instance, filename):
    _, ext = os.path.splitext(filename or '')
    safe_ext = ext.lower() if ext.lower() in ('.png', '.jpg', '.jpeg') else '.png'
    return f"branding/history/v{instance.version_number}_{uuid.uuid4()}{safe_ext}"


class CompanyProfile(models.Model):
    """
    Central Company Profile & Branding configuration managed exclusively by Super Admins.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=32, unique=True, default='default', editable=False)
    legal_name = models.CharField(
        _('Legal Name'),
        max_length=200,
        default='Northern Highways Transporters SACCO Limited',
    )
    trading_name = models.CharField(
        _('Trading Name'),
        max_length=200,
        default='Northern Highways Transporters SACCO',
    )
    short_name = models.CharField(_('Short Code / Acronym'), max_length=40, default='NHT-SMS')
    registration_number = models.CharField(_('SACCO Registration Number'), max_length=100, blank=True, default='CS/NHT/001')
    tax_pin = models.CharField(_('KRA PIN / Tax ID'), max_length=50, blank=True, default='')
    physical_address = models.CharField(
        _('Physical Address'),
        max_length=255,
        blank=True,
        default='Northern Highways Plaza, Isiolo Town, Kenya',
    )
    postal_address = models.CharField(_('Postal Address'), max_length=150, blank=True, default='P.O. Box 100 - 60300, Isiolo')
    phone_numbers = models.CharField(_('Telephone Numbers'), max_length=150, blank=True, default='+254 700 000 000')
    official_email = models.EmailField(_('Official Email'), blank=True, default='info@northernhighways.co.ke')
    website = models.URLField(_('Website'), blank=True, default='https://nhtsms.bagovi.com')
    public_base_url = models.URLField(
        _('Public Verification Base URL'),
        default='https://nhtsms.bagovi.com',
        help_text=_('Base HTTPS URL embedded in QR compliance verification links'),
    )
    footer_text = models.CharField(
        _('Official Document Footer'),
        max_length=300,
        blank=True,
        default='Northern Highways Transporters SACCO Limited | Regulated PSV Cooperative',
    )
    primary_color = models.CharField(_('Primary Brand Color (Hex)'), max_length=16, default='#10315C')
    secondary_color = models.CharField(_('Secondary Accent Color (Hex)'), max_length=16, default='#FF8A00')
    logo = models.ImageField(
        _('Official Company Logo'),
        upload_to=branding_logo_upload_path,
        validators=[validate_company_logo],
        null=True,
        blank=True,
    )
    monochrome_logo = models.ImageField(
        _('Monochrome Logo (Optional)'),
        upload_to=branding_logo_upload_path,
        validators=[validate_company_logo],
        null=True,
        blank=True,
    )
    current_version = models.PositiveIntegerField(_('Active Branding Version'), default=1)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_profile_updates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations_company_profile'
        verbose_name = _('Company Profile & Branding')
        verbose_name_plural = _('Company Profiles & Branding')

    def __str__(self):
        return f"{self.trading_name} (Branding v{self.current_version})"

    def to_snapshot_dict(self):
        return {
            'legal_name': self.legal_name,
            'trading_name': self.trading_name,
            'short_name': self.short_name,
            'registration_number': self.registration_number,
            'tax_pin': self.tax_pin,
            'physical_address': self.physical_address,
            'postal_address': self.postal_address,
            'phone_numbers': self.phone_numbers,
            'official_email': self.official_email,
            'website': self.website,
            'public_base_url': self.public_base_url,
            'footer_text': self.footer_text,
            'primary_color': self.primary_color,
            'secondary_color': self.secondary_color,
        }

    @classmethod
    def get_active(cls):
        profile = cls.objects.filter(key='default').first()
        if profile is None:
            with transaction.atomic():
                profile, created = cls.objects.get_or_create(key='default')
                if created or not profile.versions.exists():
                    profile.create_branding_version(notes='Initial default branding profile', bump_version=False)
        elif not profile.versions.exists():
            profile.create_branding_version(notes='Baseline branding snapshot', bump_version=False)
        return profile

    def get_latest_version(self):
        latest = self.versions.order_by('-version_number').first()
        if latest is None:
            latest = self.create_branding_version(notes='Baseline branding snapshot', bump_version=False)
        return latest

    def create_branding_version(self, user=None, notes='', bump_version=True):
        with transaction.atomic():
            if bump_version:
                last = self.versions.order_by('-version_number').first()
                next_ver = (last.version_number + 1) if last else max(1, self.current_version)
                self.current_version = next_ver
                self.updated_by = user
                self.save(update_fields=['current_version', 'updated_by', 'updated_at'])
            else:
                next_ver = self.current_version or 1

            version_obj = BrandingVersion(
                company_profile=self,
                version_number=next_ver,
                profile_snapshot=self.to_snapshot_dict(),
                change_notes=notes,
                created_by=user,
            )

            if self.logo and self.logo.name:
                try:
                    self.logo.open('rb')
                    logo_bytes = self.logo.read()
                    self.logo.close()
                    version_obj.logo_sha256 = hashlib.sha256(logo_bytes).hexdigest()
                    filename = os.path.basename(self.logo.name)
                    version_obj.logo_archive.save(filename, ContentFile(logo_bytes), save=False)
                except Exception:
                    pass

            if self.monochrome_logo and self.monochrome_logo.name:
                try:
                    self.monochrome_logo.open('rb')
                    mono_bytes = self.monochrome_logo.read()
                    self.monochrome_logo.close()
                    mono_filename = os.path.basename(self.monochrome_logo.name)
                    version_obj.monochrome_logo_archive.save(mono_filename, ContentFile(mono_bytes), save=False)
                except Exception:
                    pass

            version_obj.save()
            return version_obj


class BrandingVersion(models.Model):
    """
    Immutable historical snapshot of CompanyProfile & logo assets.
    Official documents reference a BrandingVersion so previously issued documents
    retain their original branding even after the active logo or profile changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_profile = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version_number = models.PositiveIntegerField(_('Version Number'), db_index=True)
    profile_snapshot = models.JSONField(_('Profile Metadata Snapshot'), default=dict)
    logo_archive = models.FileField(
        _('Archived Logo Copy'),
        upload_to=branding_history_upload_path,
        null=True,
        blank=True,
    )
    monochrome_logo_archive = models.FileField(
        _('Archived Monochrome Logo Copy'),
        upload_to=branding_history_upload_path,
        null=True,
        blank=True,
    )
    logo_sha256 = models.CharField(_('Logo SHA-256'), max_length=64, blank=True)
    change_notes = models.TextField(_('Change Notes'), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_branding_versions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integrations_branding_version'
        verbose_name = _('Branding Version Snapshot')
        verbose_name_plural = _('Branding Version Snapshots')
        ordering = ['-version_number']
        constraints = [
            models.UniqueConstraint(fields=['company_profile', 'version_number'], name='uniq_branding_profile_version'),
        ]

    def __str__(self):
        name = (self.profile_snapshot or {}).get('trading_name', 'Company Branding')
        return f"{name} - v{self.version_number}"

