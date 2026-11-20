import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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

