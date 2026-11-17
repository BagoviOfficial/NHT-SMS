import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class IncidentType(models.TextChoices):
    COMPLAINT = 'COMPLAINT', 'Member / Passenger Complaint'
    ACCIDENT = 'ACCIDENT', 'Accident / Collision'
    DISCIPLINARY = 'DISCIPLINARY', 'Crew Disciplinary Issue'
    ROUTE_DISPUTE = 'ROUTE_DISPUTE', 'Route / Stage Dispute'
    BILLING_INQUIRY = 'BILLING_INQUIRY', 'Billing & Financial Inquiry'
    GENERAL_INQUIRY = 'GENERAL_INQUIRY', 'General SACCO Inquiry'


class IncidentSeverity(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    CRITICAL = 'CRITICAL', 'Critical'


class IncidentStatus(models.TextChoices):
    SUBMITTED = 'SUBMITTED', 'Submitted'
    UNDER_INVESTIGATION = 'UNDER_INVESTIGATION', 'Under Investigation / Review'
    ACTION_REQUIRED = 'ACTION_REQUIRED', 'Action Required'
    RESOLVED = 'RESOLVED', 'Resolved'
    CLOSED = 'CLOSED', 'Closed'


class Incident(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=32, unique=True, db_index=True)
    incident_type = models.CharField(max_length=32, choices=IncidentType.choices, default=IncidentType.COMPLAINT)
    severity = models.CharField(max_length=20, choices=IncidentSeverity.choices, default=IncidentSeverity.MEDIUM)
    status = models.CharField(max_length=32, choices=IncidentStatus.choices, default=IncidentStatus.SUBMITTED, db_index=True)
    
    reported_by_member = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_incidents'
    )
    vehicle = models.ForeignKey(
        'vehicles.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents'
    )
    driver = models.ForeignKey(
        'drivers.Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incidents'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True, default="")
    date_occurred = models.DateField(default=timezone.now)
    resolution_notes = models.TextField(blank=True, default="")
    
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_incidents'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ticket_number} - {self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            year = timezone.now().year
            # Generate sequential ticket number
            last = Incident.objects.filter(ticket_number__startswith=f"NHT-INC-{year}-").order_by('-ticket_number').first()
            if last:
                try:
                    last_seq = int(last.ticket_number.split('-')[-1])
                    seq = last_seq + 1
                except Exception:
                    seq = 1
            else:
                seq = 1
            self.ticket_number = f"NHT-INC-{year}-{seq:04d}"
        super().save(*args, **kwargs)


class IncidentUpdate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='updates')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField()
    status_change = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Update for {self.incident.ticket_number} at {self.created_at}"
