import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from nht_sacco.apps.vehicles.models import Vehicle

class Route(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route_code = models.CharField(_('Route Code'), max_length=20, unique=True, db_index=True)
    name = models.CharField(_('Route Name'), max_length=150, help_text=_('e.g. Nairobi - Isiolo - Moyale Express'))
    origin = models.CharField(_('Origin Terminal'), max_length=100)
    destination = models.CharField(_('Destination Terminal'), max_length=100)
    distance_km = models.DecimalField(_('Distance (KM)'), max_digits=7, decimal_places=2)
    intermediate_stops = models.JSONField(_('Intermediate Stops'), default=list, blank=True)
    is_active = models.BooleanField(_('Active Route'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'routes_route'
        verbose_name = _('Transport Route')
        verbose_name_plural = _('Transport Routes')
        ordering = ['route_code']

    def __str__(self):
        return f"{self.route_code}: {self.origin} -> {self.destination} ({self.distance_km} KM)"


class VehicleRouteAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='route_allocations')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='allocated_vehicles')
    road_service_license = models.CharField(_('RSL / Permit Reference'), max_length=50, blank=True)
    assigned_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='route_authorizations'
    )

    class Meta:
        db_table = 'routes_vehicle_assignment'
        verbose_name = _('Vehicle Route Assignment')
        verbose_name_plural = _('Vehicle Route Assignments')
        unique_together = ('vehicle', 'route', 'is_active')
