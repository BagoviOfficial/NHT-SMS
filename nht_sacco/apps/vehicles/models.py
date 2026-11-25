import hashlib
import secrets
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from nht_sacco.apps.members.models import Member

class VehicleCategory(models.TextChoices):
    MATATU_14 = 'MATATU_14', _('14-Seater PSV Matatu')
    MINIBUS_33 = 'MINIBUS_33', _('33-Seater PSV Minibus')
    BUS_50_PLUS = 'BUS_50_PLUS', _('50+ Seater Long-Distance Bus')
    PARCEL_VAN = 'PARCEL_VAN', _('Dedicated Parcel & Courier Van')

class VehicleStatus(models.TextChoices):
    PENDING = 'PENDING', _('Pending Verification')
    ACTIVE = 'ACTIVE', _('Active in Service')
    SUSPENDED = 'SUSPENDED', _('Suspended from Service')
    MAINTENANCE = 'MAINTENANCE', _('In Garage / Maintenance')
    DECOMMISSIONED = 'DECOMMISSIONED', _('Decommissioned')

class FuelType(models.TextChoices):
    DIESEL = 'DIESEL', _('Diesel')
    PETROL = 'PETROL', _('Petrol')
    ELECTRIC = 'ELECTRIC', _('Electric')
    HYBRID = 'HYBRID', _('Hybrid')

class Vehicle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration_number = models.CharField(
        _('Registration Plate'),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_('Format: KDA 123A')
    )
    chassis_number = models.CharField(_('Chassis Number'), max_length=50, unique=True)
    engine_number = models.CharField(_('Engine Number'), max_length=50, unique=True)
    make = models.CharField(_('Make'), max_length=50, help_text=_('e.g. Toyota, Isuzu, Scania'))
    model = models.CharField(_('Model'), max_length=50, help_text=_('e.g. HiAce, NQR, FVR'))
    year_of_manufacture = models.PositiveIntegerField(_('Year of Manufacture'))
    category = models.CharField(
        _('Vehicle Category'),
        max_length=30,
        choices=VehicleCategory.choices,
        default=VehicleCategory.MATATU_14
    )
    fuel_type = models.CharField(
        _('Fuel Type'),
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.DIESEL
    )
    carrying_capacity = models.PositiveIntegerField(
        _('Carrying Capacity'),
        help_text=_('Seating capacity for passengers or tonnage')
    )
    color = models.CharField(_('Color'), max_length=50, default='White with Sacco Stripes')
    current_owner = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name='vehicles',
        verbose_name=_('Registered Owner')
    )
    status = models.CharField(
        _('Operational Status'),
        max_length=30,
        choices=VehicleStatus.choices,
        default=VehicleStatus.PENDING,
        db_index=True
    )
    qr_token = models.UUIDField(
        _('QR Verification Token'),
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_vehicles'
    )

    class Meta:
        db_table = 'vehicles_vehicle'
        verbose_name = _('Fleet Vehicle')
        verbose_name_plural = _('Fleet Vehicles')
        ordering = ['registration_number']

    def save(self, *args, **kwargs):
        # Normalize registration number to uppercase without irregular spaces
        self.registration_number = self.registration_number.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.registration_number} ({self.make} {self.model}) - {self.get_status_display()}"


class VehicleOwnershipHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='ownership_history')
    previous_owner = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='transferred_vehicles')
    new_owner = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='acquired_vehicles')
    transfer_date = models.DateTimeField(auto_now_add=True)
    transfer_reason = models.TextField(blank=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authorized_transfers'
    )

    class Meta:
        db_table = 'vehicles_ownership_history'
        verbose_name = _('Vehicle Ownership Transfer')
        verbose_name_plural = _('Vehicle Ownership Transfers')
        ordering = ['-transfer_date']


class VehiclePhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField(upload_to='public/vehicle_photos/')
    caption = models.CharField(max_length=150, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vehicles_photo'
        verbose_name = _('Vehicle Photo')
        verbose_name_plural = _('Vehicle Photos')


class ComplianceCardStatus(models.TextChoices):
    VALID = 'VALID', _('Valid & Active')
    EXPIRED = 'EXPIRED', _('Expired')
    REVOKED = 'REVOKED', _('Revoked')
    SUSPENDED = 'SUSPENDED', _('Suspended')
    SUPERSEDED = 'SUPERSEDED', _('Superseded')


class VehicleComplianceCard(models.Model):
    """
    Issued digital & printable Vehicle Compliance Card with cryptographically
    hashed QR verification token and immutable branding snapshot reference.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='compliance_cards',
    )
    certificate_number = models.CharField(
        _('Certificate Number'),
        max_length=50,
        unique=True,
        db_index=True,
    )
    fleet_number = models.CharField(_('Fleet / Reference Number'), max_length=50, blank=True)
    owner_display_name = models.CharField(_('Registered Owner / Operator'), max_length=200, blank=True)
    assigned_route_name = models.CharField(_('Assigned Route'), max_length=200, blank=True)
    token_hash = models.CharField(
        _('Verification Token SHA-256 Hash'),
        max_length=64,
        unique=True,
        db_index=True,
    )
    token_hint = models.CharField(_('Non-Secret Token Prefix'), max_length=12, blank=True)
    encrypted_token = models.TextField(
        _('Encrypted Verification Token'),
        blank=True,
        help_text=_('AES-256 encrypted copy used strictly for authorized card re-printing'),
    )
    status = models.CharField(
        _('Certificate Status'),
        max_length=20,
        choices=ComplianceCardStatus.choices,
        default=ComplianceCardStatus.VALID,
        db_index=True,
    )
    issue_date = models.DateField(_('Issue Date'), default=timezone.localdate)
    expiry_date = models.DateField(_('Expiry Date'), db_index=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_compliance_cards',
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_compliance_cards',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True)
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaces_cards',
    )
    branding_version = models.ForeignKey(
        'integrations.BrandingVersion',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='compliance_cards',
        help_text=_('Immutable branding snapshot captured when this card was issued'),
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'vehicles_compliance_card'
        verbose_name = _('Vehicle Compliance Card')
        verbose_name_plural = _('Vehicle Compliance Cards')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['vehicle', 'status']),
            models.Index(fields=['expiry_date', 'status']),
        ]

    def __str__(self):
        return f"{self.certificate_number} - {self.vehicle.registration_number} [{self.status}]"

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256((raw_token or '').strip().encode('utf-8')).hexdigest()

    @staticmethod
    def generate_raw_token() -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    def generate_certificate_number(cls) -> str:
        from nht_sacco.apps.integrations.models import NumberSequence
        return NumberSequence.next_number(
            prefix='NHT-CMP',
            year=timezone.localdate().year,
            model_cls=cls,
            field_name='certificate_number',
        )
