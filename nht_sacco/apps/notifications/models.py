import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationChannel(models.TextChoices):
    SMS = 'SMS', "Africa's Talking SMS"
    WHATSAPP = 'WHATSAPP', "Meta WhatsApp"
    EMAIL = 'EMAIL', "Email (SMTP)"
    IN_APP = 'IN_APP', "In-App Notification"


class NotificationStatus(models.TextChoices):
    QUEUED = 'QUEUED', 'Queued'
    SENT = 'SENT', 'Sent to Provider'
    DELIVERED = 'DELIVERED', 'Delivered'
    FAILED = 'FAILED', 'Delivery Failed'
    READ = 'READ', 'Read by Recipient'


class NotificationCategory(models.TextChoices):
    COMPLIANCE = 'COMPLIANCE', 'Compliance Alert'
    BILLING = 'BILLING', 'Billing & Invoicing'
    PAYMENT = 'PAYMENT', 'Payment Confirmation'
    RENEWAL = 'RENEWAL', 'Document Renewal Update'
    ANNOUNCEMENT = 'ANNOUNCEMENT', 'General SACCO Announcement'
    ACCOUNT = 'ACCOUNT', 'Account Security'


class NotificationTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=128)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.SMS)
    subject = models.CharField(max_length=255, blank=True, default="")
    body_template = models.TextField(help_text="Message body template supporting {placeholder} syntax")
    meta_template_name = models.CharField(max_length=128, blank=True, default="", help_text="Official Meta WhatsApp template name if applicable")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.get_channel_display()})"


class CommunicationPreference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField(
        'members.Member',
        on_delete=models.CASCADE,
        related_name='communication_preference'
    )
    sms_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    
    compliance_alerts = models.BooleanField(default=True)
    billing_alerts = models.BooleanField(default=True)
    renewal_alerts = models.BooleanField(default=True)
    announcements = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.member.membership_number}"

    def is_channel_allowed(self, channel: str) -> bool:
        if channel == NotificationChannel.SMS:
            return self.sms_enabled
        if channel == NotificationChannel.WHATSAPP:
            return self.whatsapp_enabled
        if channel == NotificationChannel.EMAIL:
            return self.email_enabled
        if channel == NotificationChannel.IN_APP:
            return self.in_app_enabled
        return True


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    recipient_member = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    recipient_phone = models.CharField(max_length=20, blank=True, default="")
    recipient_email = models.EmailField(blank=True, default="")
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    category = models.CharField(max_length=20, choices=NotificationCategory.choices, default=NotificationCategory.COMPLIANCE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.QUEUED, db_index=True)
    external_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    delivery_attempts = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.channel}] {self.title} to {self.recipient_phone or self.recipient_email or self.recipient_user} ({self.status})"

    def mark_as_read(self):
        if self.status != NotificationStatus.READ:
            self.status = NotificationStatus.READ
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])


class NotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=NotificationStatus.choices)
    provider_response = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Log #{self.attempt_number} for {self.notification_id}: {self.status}"


class AnnouncementPriority(models.TextChoices):
    NORMAL = 'NORMAL', 'Normal'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=AnnouncementPriority.choices, default=AnnouncementPriority.NORMAL)
    is_published = models.BooleanField(default=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='published_announcements'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.priority}] {self.title}"
