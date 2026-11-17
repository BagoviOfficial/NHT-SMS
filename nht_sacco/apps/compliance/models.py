import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from nht_sacco.apps.vehicles.models import Vehicle
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.documents.models import Document

class ComplianceStatus(models.TextChoices):
    FULLY_COMPLIANT = 'FULLY_COMPLIANT', _('Fully Compliant')
    EXPIRING_SOON = 'EXPIRING_SOON', _('Expiring Soon (Warning)')
    NON_COMPLIANT = 'NON_COMPLIANT', _('Non-Compliant (Expired / Missing)')

class ComplianceAlert(models.Model):
    class AlertType(models.TextChoices):
        UPCOMING_EXPIRY = 'UPCOMING_EXPIRY', _('Upcoming Expiry Warning')
        EXPIRED = 'EXPIRED', _('Document Expired')
        MISSING_DOCUMENT = 'MISSING_DOCUMENT', _('Mandatory Document Missing')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='compliance_alerts')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    days_remaining = models.IntegerField(_('Days Remaining / Overdue'))
    message = models.TextField()
    recipient_member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='compliance_alerts')
    is_resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'compliance_alert'
        verbose_name = _('Compliance Alert')
        verbose_name_plural = _('Compliance Alerts')
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.alert_type}] {self.vehicle.registration_number}: {self.message[:60]}"
