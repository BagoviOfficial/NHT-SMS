from django.contrib import admin
from .models import (
    NotificationTemplate,
    CommunicationPreference,
    Notification,
    NotificationLog,
    Announcement,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'channel', 'is_active', 'updated_at')
    list_filter = ('channel', 'is_active')
    search_fields = ('code', 'name', 'subject')


@admin.register(CommunicationPreference)
class CommunicationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('member', 'sms_enabled', 'whatsapp_enabled', 'email_enabled', 'in_app_enabled', 'compliance_alerts', 'billing_alerts')
    search_fields = ('member__membership_number', 'member__first_name', 'member__last_name')


class NotificationLogInLine(admin.TabularInline):
    model = NotificationLog
    extra = 0
    readonly_fields = ('attempt_number', 'status', 'provider_response', 'created_at')
    can_delete = False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'channel', 'category', 'status', 'recipient_phone', 'recipient_email', 'created_at')
    list_filter = ('channel', 'category', 'status', 'created_at')
    search_fields = ('title', 'recipient_phone', 'recipient_email', 'external_id')
    readonly_fields = ('created_at', 'sent_at', 'delivered_at', 'read_at', 'external_id')
    inlines = [NotificationLogInLine]


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'is_published', 'published_by', 'created_at')
    list_filter = ('priority', 'is_published', 'created_at')
    search_fields = ('title', 'content')
