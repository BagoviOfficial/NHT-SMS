import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MaintenanceType(models.TextChoices):
    SCHEDULED_SERVICE = 'SCHEDULED_SERVICE', _('Routine / Scheduled Service')
    UNSCHEDULED_REPAIR = 'UNSCHEDULED_REPAIR', _('Breakdown / Unscheduled Repair')
    INSPECTION_PREP = 'INSPECTION_PREP', _('NTSA Inspection Preparation')
    TYRE_SERVICE = 'TYRE_SERVICE', _('Tyre Replacement / Wheel Alignment')
    BODY_ACCIDENT = 'BODY_ACCIDENT', _('Bodywork / Accident Repair')


class MaintenanceStatus(models.TextChoices):
    BOOKED = 'BOOKED', _('Scheduled / Booked')
    IN_PROGRESS = 'IN_PROGRESS', _('In Progress at Garage')
    COMPLETED = 'COMPLETED', _('Completed & Cleared')
    CANCELLED = 'CANCELLED', _('Cancelled')


class MaintenanceProvider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Workshop / Garage Name'), max_length=200, unique=True)
    contact_person = models.CharField(_('Contact Person'), max_length=150)
    phone_number = models.CharField(_('Phone Number'), max_length=20)
    email = models.EmailField(_('Email Address'), blank=True, default='')
    physical_address = models.CharField(_('Physical Location'), max_length=255)
    is_approved = models.BooleanField(_('Approved SACCO Vendor'), default=True)
    specialty = models.CharField(_('Specialty'), max_length=150, blank=True, default='General Mechanical & Electrical')
    notes = models.TextField(_('Notes'), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Maintenance Provider')
        verbose_name_plural = _('Maintenance Providers')

    def __str__(self):
        return f"{self.name} ({self.physical_address})"


class SparePart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Part Name'), max_length=200)
    part_number = models.CharField(_('Part Number / OEM Ref'), max_length=100, blank=True, default='')
    category = models.CharField(_('Category'), max_length=100, default='General')
    unit_cost = models.DecimalField(_('Unit Cost (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    quantity_in_stock = models.IntegerField(_('Quantity in Stock'), default=0)
    minimum_reorder_level = models.IntegerField(_('Reorder Level'), default=5)

    class Meta:
        ordering = ['name']
        verbose_name = _('Spare Part')
        verbose_name_plural = _('Spare Parts')

    def __str__(self):
        return f"{self.name} [{self.part_number}] - KES {self.unit_cost}"


class MaintenanceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order_number = models.CharField(
        _('Work Order Number'),
        max_length=32,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-MNT-YYYY-XXXX')
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.CASCADE,
        related_name='maintenance_records',
        verbose_name=_('Vehicle')
    )
    provider = models.ForeignKey(
        MaintenanceProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='records',
        verbose_name=_('Service Provider')
    )
    maintenance_type = models.CharField(
        _('Maintenance Type'),
        max_length=32,
        choices=MaintenanceType.choices,
        default=MaintenanceType.SCHEDULED_SERVICE
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.BOOKED,
        db_index=True
    )
    scheduled_date = models.DateField(_('Scheduled Date'), default=timezone.now)
    completed_date = models.DateField(_('Completion Date'), null=True, blank=True)
    odometer_reading = models.PositiveIntegerField(
        _('Odometer Reading (KM)'),
        default=0,
        help_text=_('Current vehicle mileage at servicing')
    )
    downtime_hours = models.DecimalField(
        _('Downtime (Hours)'),
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Hours vehicle was out of revenue operations')
    )
    parts_cost = models.DecimalField(
        _('Parts Cost (KES)'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    labour_cost = models.DecimalField(
        _('Labour Cost (KES)'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_cost = models.DecimalField(
        _('Total Maintenance Cost (KES)'),
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    description = models.TextField(_('Work Performed / Fault Symptoms'))
    technician_notes = models.TextField(_('Technician Notes'), blank=True, default='')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_maintenance'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_maintenance'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date', '-created_at']
        verbose_name = _('Maintenance Record')
        verbose_name_plural = _('Maintenance Records')

    def __str__(self):
        return f"{self.work_order_number} - {self.vehicle.registration_number} ({self.get_maintenance_type_display()})"

    def save(self, *args, **kwargs):
        if not self.work_order_number:
            year = timezone.now().year
            last = MaintenanceRecord.objects.filter(work_order_number__startswith=f"NHT-MNT-{year}-").order_by('-work_order_number').first()
            if last:
                try:
                    last_seq = int(last.work_order_number.split('-')[-1])
                    seq = last_seq + 1
                except Exception:
                    seq = 1
            else:
                seq = 1
            self.work_order_number = f"NHT-MNT-{year}-{seq:04d}"

        # Recompute total cost
        self.total_cost = self.parts_cost + self.labour_cost
        super().save(*args, **kwargs)


class MaintenancePartUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    maintenance_record = models.ForeignKey(
        MaintenanceRecord,
        on_delete=models.CASCADE,
        related_name='parts_used'
    )
    part = models.ForeignKey(SparePart, on_delete=models.PROTECT, related_name='usages')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = _('Part Usage')
        verbose_name_plural = _('Parts Usages')

    def __str__(self):
        return f"{self.quantity}x {self.part.name} on {self.maintenance_record.work_order_number}"
