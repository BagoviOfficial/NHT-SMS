from django.contrib import admin
from django.utils.html import format_html
from .models import (
    SystemConfiguration,
    ConfigurationHistory,
    IntegrationHealthLog,
    CompanyProfile,
    BrandingVersion,
    NumberSequence,
)
from .crypto import CryptoService
from .services import ConfigurationService


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        'key',
        'title',
        'category',
        'data_type',
        'masked_value_display',
        'is_secret',
        'version',
        'updated_at',
    ]
    list_filter = ['category', 'data_type', 'is_secret', 'is_system_locked', 'requires_restart']
    search_fields = ['key', 'title', 'description']
    readonly_fields = ['version', 'updated_by', 'created_at', 'updated_at']
    fieldsets = (
        ('Registry Metadata', {
            'fields': ('key', 'category', 'title', 'description', 'data_type')
        }),
        ('Value & Validation', {
            'fields': ('raw_value', 'default_value', 'is_secret', 'validation_regex', 'choices_json')
        }),
        ('System Flags & Governance', {
            'fields': ('is_system_locked', 'requires_restart', 'requires_approval')
        }),
        ('Audit Tracking', {
            'fields': ('version', 'updated_by', 'created_at', 'updated_at')
        }),
    )

    def masked_value_display(self, obj):
        if obj.is_secret:
            return format_html('<span class="text-muted"><code>{}</code></span>', CryptoService.mask_secret(obj.raw_value))
        val = ConfigurationService._cast_value(obj.raw_value, obj.data_type, is_secret=False)
        return str(val)[:50]
    masked_value_display.short_description = 'Value'

    def save_model(self, request, obj, form, change):
        # Delegate to ConfigurationService for atomic versioning and history tracking
        if change:
            ConfigurationService.set(
                key=obj.key,
                value=obj.raw_value,
                user=request.user,
                reason="Updated via Django Admin interface",
                ip_address=request.META.get('REMOTE_ADDR')
            )
        else:
            obj.updated_by = request.user
            if obj.is_secret:
                obj.raw_value = CryptoService.encrypt(obj.raw_value)
            super().save_model(request, obj, form, change)


@admin.register(ConfigurationHistory)
class ConfigurationHistoryAdmin(admin.ModelAdmin):
    list_display = ['setting', 'version', 'changed_by_username', 'ip_address', 'reason', 'timestamp']
    list_filter = ['timestamp', 'setting__category']
    search_fields = ['setting__key', 'changed_by_username', 'reason']
    readonly_fields = [
        'setting',
        'version',
        'old_value',
        'new_value',
        'changed_by',
        'changed_by_username',
        'ip_address',
        'reason',
        'timestamp',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IntegrationHealthLog)
class IntegrationHealthLogAdmin(admin.ModelAdmin):
    list_display = ['service_name', 'status_badge', 'response_time_ms', 'tested_at', 'tested_by']
    list_filter = ['status', 'service_name', 'tested_at']
    search_fields = ['service_name', 'error_message']
    readonly_fields = [
        'service_name',
        'status',
        'response_time_ms',
        'details',
        'error_message',
        'tested_at',
        'tested_by',
    ]

    def status_badge(self, obj):
        color = 'green' if obj.status == 'HEALTHY' else 'orange' if obj.status == 'DEGRADED' else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">● {}</span>', color, obj.status)
    status_badge.short_description = 'Health Status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ['trading_name', 'legal_name', 'short_name', 'current_version', 'updated_by', 'updated_at']
    readonly_fields = ['current_version', 'updated_by', 'created_at', 'updated_at']

    def has_add_permission(self, request):
        return not CompanyProfile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        obj.create_branding_version(user=request.user, notes="Updated via Django Admin", bump_version=True)


@admin.register(BrandingVersion)
class BrandingVersionAdmin(admin.ModelAdmin):
    list_display = ['company_profile', 'version_number', 'logo_sha256', 'created_by', 'created_at']
    readonly_fields = ['company_profile', 'version_number', 'profile_snapshot', 'logo_archive', 'monochrome_logo_archive', 'logo_sha256', 'change_notes', 'created_by', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NumberSequence)
class NumberSequenceAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'year', 'last_number', 'updated_at']
    search_fields = ['prefix']
    readonly_fields = ['prefix', 'year', 'last_number', 'updated_at']

    def has_delete_permission(self, request, obj=None):
        return False
