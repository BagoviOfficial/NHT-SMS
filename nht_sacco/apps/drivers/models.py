import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from nht_sacco.apps.vehicles.models import Vehicle

class DriverStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active Authorized Driver')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    ON_LEAVE = 'ON_LEAVE', _('On Leave')
    INACTIVE = 'INACTIVE', _('Inactive')

class Driver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_profile',
        verbose_name=_('Linked User Account')
    )
    full_name = models.CharField(_('Full Name'), max_length=150)
    national_id = models.CharField(_('National ID'), max_length=30, unique=True, db_index=True)
    phone_number = models.CharField(_('Phone Number'), max_length=20, unique=True)
    driving_license_number = models.CharField(_('Driving License Number'), max_length=30, unique=True)
    dl_expiry_date = models.DateField(_('DL Expiry Date'), db_index=True)
    psv_badge_number = models.CharField(_('NTSA PSV Badge Number'), max_length=30, blank=True)
    psv_badge_expiry = models.DateField(_('PSV Badge Expiry Date'), null=True, blank=True)
    emergency_contact_name = models.CharField(_('Emergency Contact Person'), max_length=150)
    emergency_contact_phone = models.CharField(_('Emergency Contact Phone'), max_length=20)
    status = models.CharField(
        _('Driver Status'),
        max_length=20,
        choices=DriverStatus.choices,
        default=DriverStatus.ACTIVE,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drivers_driver'
        verbose_name = _('SACCO Driver')
        verbose_name_plural = _('SACCO Drivers')
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} (DL: {self.driving_license_number}) - {self.get_status_display()}"


class DriverAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='assignments')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='driver_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)
    relieved_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='driver_assignments'
    )
    is_current = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'drivers_assignment'
        verbose_name = _('Driver Assignment')
        verbose_name_plural = _('Driver Assignments')
        ordering = ['-assigned_at']

    def relieve(self):
        from django.utils import timezone
        self.is_current = False
        self.relieved_at = timezone.now()
        self.save(update_fields=['is_current', 'relieved_at'])
