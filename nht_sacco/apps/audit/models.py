import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class AuditAction(models.TextChoices):
    LOGIN = 'LOGIN', _('User Login')
    LOGOUT = 'LOGOUT', _('User Logout')
    VIEW = 'VIEW', _('Record Accessed / Viewed')
    CREATE = 'CREATE', _('Record Created')
    UPDATE = 'UPDATE', _('Record Updated')
    DELETE = 'DELETE', _('Record Deleted')
    APPROVE = 'APPROVE', _('Workflow Approved')
    REJECT = 'REJECT', _('Workflow Rejected')
    PAYMENT = 'PAYMENT', _('Payment Processed')
    REVERSAL = 'REVERSAL', _('Financial Reversal')
    EXPORT = 'EXPORT', _('Data Export')
    SYSTEM = 'SYSTEM', _('System / Background Operation')

class AuditOutcome(models.TextChoices):
    SUCCESS = 'SUCCESS', _('Success')
    FAILED = 'FAILED', _('Failed')
    DENIED = 'DENIED', _('Access Denied')

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_actions'
    )
    actor_username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=30, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True)
    entity_id = models.CharField(max_length=100, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    change_details = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=20, choices=AuditOutcome.choices, default=AuditOutcome.SUCCESS)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_log'
        verbose_name = _('Audit Log Entry')
        verbose_name_plural = _('Audit Log Entries')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['action', 'timestamp']),
        ]

    @classmethod
    def log_action(cls, actor=None, action=AuditAction.SYSTEM, entity_type='SYSTEM', entity_id='', outcome=AuditOutcome.SUCCESS, notes='', ip_address=None, change_details=None):
        details = change_details or {}
        if notes:
            details['notes'] = notes
        return cls.objects.create(
            actor=actor,
            actor_username=actor.username if actor else 'SYSTEM',
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else '',
            ip_address=ip_address,
            outcome=outcome,
            change_details=details
        )

    def __str__(self):
        actor_name = self.actor_username or (self.actor.username if self.actor else 'SYSTEM')
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {actor_name} - {self.action} on {self.entity_type}:{self.entity_id} ({self.outcome})"

    def clean(self):
        if not self._state.adding:
            raise ValidationError(_('Audit log entries are immutable and cannot be modified.'))

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_('Audit log entries are immutable and cannot be updated.'))
        if self.actor and not self.actor_username:
            self.actor_username = self.actor.username
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_('Audit log entries are permanent and cannot be deleted.'))
