import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from nht_sacco.apps.vehicles.models import Vehicle
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.drivers.models import Driver
from .validators import validate_regulatory_document

class DocumentCategory(models.TextChoices):
    INSPECTION = 'INSPECTION', _('Vehicle Inspection Certificate')
    INSURANCE = 'INSURANCE', _('Motor Commercial Insurance Certificate')
    KENHA_PERMIT = 'KENHA_PERMIT', _('KeNHA Road Authority Permit')
    NTSA_RSL = 'NTSA_RSL', _('NTSA Road Service Licence')
    COUNTY_PERMIT = 'COUNTY_PERMIT', _('County Transport Business Permit')
    SPEED_GOVERNOR = 'SPEED_GOVERNOR', _('Speed Governor Certificate')
    POLICE_CLEARANCE = 'POLICE_CLEARANCE', _('Police Clearance / Good Conduct')
    DRIVER_LICENSE = 'DRIVER_LICENSE', _('Driving License Commercial Endorsement')
    SACCO_DOC = 'SACCO_DOC', _('SACCO Agreement / Bylaws')
    OTHER = 'OTHER', _('Other Approved Document')

class VerificationStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Verification')
    VERIFIED = 'VERIFIED', _('Verified & Approved')
    REJECTED = 'REJECTED', _('Rejected / Incomplete')
    EXPIRED = 'EXPIRED', _('Expired')
    SUPERSEDED = 'SUPERSEDED', _('Superseded by New Version')

class DocumentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Document Type Name'), max_length=150, unique=True)
    category = models.CharField(_('Regulatory Category'), max_length=40, choices=DocumentCategory.choices)
    standard_validity_months = models.PositiveIntegerField(
        _('Standard Validity (Months)'),
        default=12,
        help_text=_('Normal validity period in months (e.g. 12 for annual, 6 for inspection)')
    )
    reminder_thresholds = models.JSONField(
        _('Reminder Thresholds (Days)'),
        default=list,
        help_text=_('List of days before expiry to alert, e.g. [30, 14, 7, 3, 0]')
    )
    is_mandatory_for_vehicle = models.BooleanField(_('Mandatory for Vehicle Fleet Compliance'), default=False)
    is_mandatory_for_driver = models.BooleanField(_('Mandatory for Driver Certification'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documents_type'
        verbose_name = _('Document Type')
        verbose_name_plural = _('Document Types')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


def private_document_upload_path(instance, filename):
    ext = filename.split('.')[-1]
    return f"regulatory_documents/{instance.document_type.category}/{uuid.uuid4()}.{ext}"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name='documents')
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='compliance_documents'
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='regulatory_documents'
    )
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='compliance_documents'
    )
    reference_number = models.CharField(
        _('Certificate / Policy Number'),
        max_length=100,
        db_index=True
    )
    issue_date = models.DateField(_('Date of Issue'))
    expiry_date = models.DateField(_('Expiry Date'), db_index=True)
    file = models.FileField(
        _('Document File (Private Vault)'),
        upload_to=private_document_upload_path,
        validators=[validate_regulatory_document]
    )
    file_hash = models.CharField(_('SHA-256 Checksum'), max_length=64, blank=True)
    version = models.PositiveIntegerField(_('Version Number'), default=1)
    status = models.CharField(
        _('Verification Status'),
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_documents'
    )
    verification_date = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents_document'
        verbose_name = _('Compliance Document')
        verbose_name_plural = _('Compliance Documents')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vehicle', 'document_type', 'status']),
            models.Index(fields=['expiry_date', 'status']),
        ]

    def __str__(self):
        target = self.vehicle.registration_number if self.vehicle else (self.driver.full_name if self.driver else str(self.member))
        return f"{self.document_type.name} [{self.reference_number}] for {target} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Calculate SHA-256 checksum for audit and tamper detection
        if self.file and not self.file_hash:
            try:
                hasher = hashlib.sha256()
                for chunk in self.file.chunks():
                    hasher.update(chunk)
                self.file_hash = hasher.hexdigest()
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        from django.utils import timezone
        return self.expiry_date < timezone.localdate()

    @property
    def days_to_expiry(self):
        from django.utils import timezone
        return (self.expiry_date - timezone.localdate()).days


class DocumentVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='verifications')
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_reviews'
    )
    decision = models.CharField(max_length=20, choices=[('APPROVED', 'Approved'), ('REJECTED', 'Rejected')])
    notes = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'documents_verification_history'
        verbose_name = _('Document Verification Record')
        verbose_name_plural = _('Document Verification Records')
        ordering = ['-timestamp']
