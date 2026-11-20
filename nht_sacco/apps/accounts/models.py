import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class UserRole(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', _('Super Administrator')
    CHAIRMAN = 'CHAIRMAN', _('SACCO Chairman')
    SECRETARY = 'SECRETARY', _('SACCO Secretary')
    TREASURER = 'TREASURER', _('SACCO Treasurer')
    ACCOUNTANT = 'ACCOUNTANT', _('Accountant')
    COMPLIANCE_OFFICER = 'COMPLIANCE_OFFICER', _('Compliance Officer')
    RENEWAL_OFFICER = 'RENEWAL_OFFICER', _('Renewal Officer')
    FIELD_OFFICER = 'FIELD_OFFICER', _('Field Officer')
    AUDITOR = 'AUDITOR', _('Auditor')
    MEMBER = 'MEMBER', _('SACCO Member')

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('Email Address'), unique=True)
    phone_number = models.CharField(
        _('Phone Number'),
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Format: +2547XXXXXXXX')
    )
    national_id = models.CharField(
        _('National ID / Passport'),
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )
    role = models.CharField(
        _('System Role'),
        max_length=30,
        choices=UserRole.choices,
        default=UserRole.MEMBER,
        db_index=True
    )
    must_change_password = models.BooleanField(
        _('Must Change Password'),
        default=False
    )
    last_login_ip = models.GenericIPAddressField(
        _('Last Login IP'),
        null=True,
        blank=True
    )
    is_verified = models.BooleanField(
        _('Identity Verified'),
        default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_user'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def __str__(self):
        full_name = self.get_full_name()
        return f"{full_name} ({self.username}) - {self.get_role_display()}" if full_name else f"{self.username} - {self.get_role_display()}"

    def save(self, *args, **kwargs):
        # Defend against django_otp OTPMiddleware replacing model boolean field with a partial function
        if callable(getattr(self, 'is_verified', None)):
            if self.pk:
                orig_val = type(self).objects.filter(pk=self.pk).values_list('is_verified', flat=True).first()
                self.is_verified = bool(orig_val)
            else:
                self.is_verified = False
        super().save(*args, **kwargs)

    @property
    def is_management_staff(self):
        return self.is_superuser or self.role in [
            UserRole.SUPER_ADMIN,
            UserRole.CHAIRMAN,
            UserRole.SECRETARY,
            UserRole.TREASURER,
            UserRole.ACCOUNTANT,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.RENEWAL_OFFICER,
            UserRole.FIELD_OFFICER,
            UserRole.AUDITOR,
        ]

    @property
    def is_financial_staff(self):
        return self.is_superuser or self.role in [
            UserRole.SUPER_ADMIN,
            UserRole.TREASURER,
            UserRole.ACCOUNTANT,
        ]

    @property
    def is_compliance_staff(self):
        return self.is_superuser or self.role in [
            UserRole.SUPER_ADMIN,
            UserRole.COMPLIANCE_OFFICER,
        ]

    @property
    def is_renewal_staff(self):
        return self.is_superuser or self.role in [
            UserRole.SUPER_ADMIN,
            UserRole.RENEWAL_OFFICER,
        ]

    @property
    def is_auditor(self):
        return self.is_superuser or self.role in [
            UserRole.SUPER_ADMIN,
            UserRole.AUDITOR,
        ]

    @property
    def is_member(self):
        return self.role == UserRole.MEMBER


class LoginHistory(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')
        LOCKED_OUT = 'LOCKED_OUT', _('Locked Out')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_records'
    )
    username_attempted = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'accounts_login_history'
        verbose_name = _('Login History')
        verbose_name_plural = _('Login Histories')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.username_attempted} - {self.status} at {self.timestamp}"
