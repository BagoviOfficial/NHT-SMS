import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class MembershipCategory(models.TextChoices):
    INDIVIDUAL_OPERATOR = 'INDIVIDUAL', _('Individual Matatu / PSV Owner')
    FLEET_OWNER = 'FLEET_OWNER', _('Fleet Owner (Multiple Vehicles)')
    CORPORATE = 'CORPORATE', _('Corporate Transport Operator')

class MembershipStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Secretariat Approval')
    ACTIVE = 'ACTIVE', _('Active Member in Good Standing')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    TERMINATED = 'TERMINATED', _('Membership Terminated')

class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='member_profile',
        verbose_name=_('User Account')
    )
    membership_number = models.CharField(
        _('Membership Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-MBR-YYYY-XXXX')
    )
    first_name = models.CharField(_('First Name'), max_length=100)
    middle_name = models.CharField(_('Middle Name'), max_length=100, blank=True)
    last_name = models.CharField(_('Last Name'), max_length=100)
    national_id = models.CharField(_('National ID / Passport'), max_length=30, unique=True, db_index=True)
    phone_number = models.CharField(_('Phone Number'), max_length=20, unique=True)
    email = models.EmailField(_('Email Address'), unique=True)
    postal_address = models.CharField(_('Postal Address'), max_length=255, blank=True)
    county = models.CharField(_('County of Operation'), max_length=100, default='Isiolo')
    category = models.CharField(
        _('Membership Category'),
        max_length=30,
        choices=MembershipCategory.choices,
        default=MembershipCategory.INDIVIDUAL_OPERATOR
    )
    status = models.CharField(
        _('Membership Status'),
        max_length=30,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING,
        db_index=True
    )
    next_of_kin_name = models.CharField(_('Next of Kin Full Name'), max_length=150)
    next_of_kin_relation = models.CharField(_('Relationship'), max_length=50)
    next_of_kin_phone = models.CharField(_('Next of Kin Phone'), max_length=20)
    application_date = models.DateField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_members'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    branding_version = models.ForeignKey(
        'integrations.BrandingVersion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='member_certificates',
        help_text=_('Immutable branding snapshot captured when membership certificate is issued'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'members_member'
        verbose_name = _('SACCO Member')
        verbose_name_plural = _('SACCO Members')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.membership_number} - {self.full_name} ({self.get_status_display()})"

    @property
    def full_name(self):
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def approve(self, officer_user, notes=''):
        self.status = MembershipStatus.ACTIVE
        self.approved_by = officer_user
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.save(update_fields=['status', 'approved_by', 'approval_date', 'approval_notes', 'updated_at'])

    def suspend(self, officer_user, reason=''):
        self.status = MembershipStatus.SUSPENDED
        self.approval_notes = f"Suspended by {officer_user.username} on {timezone.now():%Y-%m-%d}: {reason}"
        self.save(update_fields=['status', 'approval_notes', 'updated_at'])

    def reinstate(self, officer_user):
        self.status = MembershipStatus.ACTIVE
        self.approval_notes = f"Reinstated by {officer_user.username} on {timezone.now():%Y-%m-%d}."
        self.save(update_fields=['status', 'approval_notes', 'updated_at'])

    @classmethod
    def generate_membership_number(cls):
        from nht_sacco.apps.integrations.models import NumberSequence
        year = timezone.now().year
        return NumberSequence.next_number(
            prefix='NHT-MBR',
            year=year,
            model_cls=cls,
            field_name='membership_number',
        )


class MemberDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='id_documents')
    document_name = models.CharField(max_length=100)
    file = models.FileField(upload_to='private/member_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'members_document'
        verbose_name = _('Member Identification Document')
        verbose_name_plural = _('Member Identification Documents')
