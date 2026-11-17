from django.contrib import admin
from .models import ComplianceAlert

@admin.register(ComplianceAlert)
class ComplianceAlertAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'alert_type', 'days_remaining', 'recipient_member', 'is_resolved', 'created_at')
    list_filter = ('alert_type', 'is_resolved', 'created_at')
    search_fields = ('vehicle__registration_number', 'recipient_member__first_name', 'recipient_member__last_name', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    actions = ['mark_as_resolved']

    @admin.action(description='Mark selected alerts as resolved')
    def mark_as_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_resolved=True, resolved_at=timezone.now())
        self.message_user(request, "Selected alerts marked as resolved.")
