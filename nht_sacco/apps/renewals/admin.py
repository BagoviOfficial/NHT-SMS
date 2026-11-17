from django.contrib import admin
from .models import RenewalRequest

@admin.register(RenewalRequest)
class RenewalRequestAdmin(admin.ModelAdmin):
    list_display = ('request_number', 'member', 'vehicle', 'document_type', 'status', 'created_at')
    list_filter = ('status', 'document_type', 'created_at')
    search_fields = ('request_number', 'member__first_name', 'member__last_name', 'vehicle__registration_number')
    ordering = ('-created_at',)
    readonly_fields = ('request_number', 'created_at', 'updated_at', 'completed_at')
