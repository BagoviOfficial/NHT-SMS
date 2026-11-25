import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.vehicles.models import Vehicle
from nht_sacco.apps.documents.models import Document, DocumentType, VerificationStatus
from nht_sacco.apps.billing.models import Invoice

class RenewalStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', _('Submitted by Member')
    UNDER_REVIEW = 'UNDER_REVIEW', _('Under Officer Review')
    INVOICED = 'INVOICED', _('Invoice Generated & Pending Payment')
    PAID = 'PAID', _('Payment Cleared - Ready for Processing')
    PROCESSING = 'PROCESSING', _('Processing with Regulatory Authority')
    DOC_UPLOADED = 'DOC_UPLOADED', _('New Official Document Uploaded')
    COMPLETED = 'COMPLETED', _('Compliance Approved & Completed')
    REJECTED = 'REJECTED', _('Application Rejected')
    CANCELLED = 'CANCELLED', _('Cancelled by Member')

class RenewalRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_number = models.CharField(
        _('Renewal Request Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-RNW-YYYY-XXXX')
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name='renewal_requests',
        verbose_name=_('Applying Member')
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name='renewal_requests',
        verbose_name=_('Fleet Vehicle')
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='renewal_requests',
        verbose_name=_('Document Type to Renew')
    )
    current_document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewal_sources',
        verbose_name=_('Expiring Document')
    )
    replacement_document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewal_outputs',
        verbose_name=_('Renewed Document')
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewal_requests',
        verbose_name=_('Associated Fee Invoice')
    )
    status = models.CharField(
        _('Renewal Workflow Status'),
        max_length=25,
        choices=RenewalStatus.choices,
        default=RenewalStatus.SUBMITTED,
        db_index=True
    )
    notes = models.TextField(_('Application Notes & Instructions'), blank=True)
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_renewals',
        verbose_name=_('Handling Renewal Officer')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'renewals_request'
        verbose_name = _('Document Renewal Request')
        verbose_name_plural = _('Document Renewal Requests')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.request_number}: {self.vehicle.registration_number} - {self.document_type.name} [{self.get_status_display()}]"

    @classmethod
    def generate_request_number(cls):
        from nht_sacco.apps.integrations.models import NumberSequence
        year = timezone.localdate().year
        return NumberSequence.next_number(
            prefix='NHT-RNW',
            year=year,
            model_cls=cls,
            field_name='request_number',
        )

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self.generate_request_number()
        super().save(*args, **kwargs)

    def mark_reviewed(self, officer_user, invoice):
        self.assigned_officer = officer_user
        self.invoice = invoice
        self.status = RenewalStatus.INVOICED
        self.save(update_fields=['assigned_officer', 'invoice', 'status', 'updated_at'])

    def mark_paid(self):
        self.status = RenewalStatus.PAID
        self.save(update_fields=['status', 'updated_at'])

    def mark_processing(self):
        self.status = RenewalStatus.PROCESSING
        self.save(update_fields=['status', 'updated_at'])

    def upload_replacement_document(self, new_doc):
        self.replacement_document = new_doc
        self.status = RenewalStatus.DOC_UPLOADED
        self.save(update_fields=['replacement_document', 'status', 'updated_at'])

    def complete_renewal(self, compliance_officer):
        self.status = RenewalStatus.COMPLETED
        self.completed_at = timezone.now()
        if self.replacement_document:
            self.replacement_document.status = VerificationStatus.VERIFIED
            self.replacement_document.verified_by = compliance_officer
            self.replacement_document.verification_date = timezone.now()
            self.replacement_document.save()
        if self.current_document:
            self.current_document.status = VerificationStatus.SUPERSEDED
            self.current_document.save()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])
