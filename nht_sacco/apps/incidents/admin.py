from django.contrib import admin
from .models import Incident, IncidentUpdate


class IncidentUpdateInline(admin.TabularInline):
    model = IncidentUpdate
    extra = 1
    readonly_fields = ('created_at',)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'incident_type', 'severity', 'status', 'reported_by_member', 'vehicle', 'date_occurred')
    list_filter = ('incident_type', 'severity', 'status', 'date_occurred')
    search_fields = ('ticket_number', 'title', 'description', 'reported_by_member__membership_number')
    readonly_fields = ('ticket_number', 'created_at', 'updated_at')
    inlines = [IncidentUpdateInline]
