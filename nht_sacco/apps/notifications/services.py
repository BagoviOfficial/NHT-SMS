import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db import transaction
from .models import (
    Notification,
    NotificationLog,
    NotificationTemplate,
    NotificationChannel,
    NotificationStatus,
    NotificationCategory,
    CommunicationPreference,
    Announcement,
)
from .adapters import (
    AfricasTalkingSMSAdapter,
    MetaWhatsAppAdapter,
    EmailNotificationAdapter,
    InAppNotificationAdapter,
)

logger = logging.getLogger(__name__)


class NotificationDispatcherService:
    ADAPTER_MAP = {
        NotificationChannel.SMS: AfricasTalkingSMSAdapter,
        NotificationChannel.WHATSAPP: MetaWhatsAppAdapter,
        NotificationChannel.EMAIL: EmailNotificationAdapter,
        NotificationChannel.IN_APP: InAppNotificationAdapter,
    }

    @classmethod
    def get_or_create_preferences(cls, member):
        pref, _ = CommunicationPreference.objects.get_or_create(member=member)
        return pref

    @classmethod
    def dispatch_to_member(
        cls,
        member,
        category: str,
        title: str,
        message: str,
        template_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
    ) -> List[Notification]:
        """
        Dispatches notification to a SACCO member across permitted channels.
        """
        context = context or {}
        pref = cls.get_or_create_preferences(member)

        # 1. Verify category permission
        if category == NotificationCategory.COMPLIANCE and not pref.compliance_alerts:
            logger.info(f"Compliance notifications disabled for member {member.membership_number}")
            return []
        if category == NotificationCategory.BILLING and not pref.billing_alerts:
            logger.info(f"Billing notifications disabled for member {member.membership_number}")
            return []
        if category == NotificationCategory.RENEWAL and not pref.renewal_alerts:
            logger.info(f"Renewal notifications disabled for member {member.membership_number}")
            return []
        if category == NotificationCategory.ANNOUNCEMENT and not pref.announcements:
            logger.info(f"Announcements disabled for member {member.membership_number}")
            return []

        # Determine target channels
        target_channels = channels or [
            NotificationChannel.IN_APP,
            NotificationChannel.SMS,
        ]

        created_notifications = []

        for ch in target_channels:
            if not pref.is_channel_allowed(ch):
                logger.info(f"Channel {ch} disabled by member {member.membership_number}")
                continue

            # Format message with template if available
            final_title = title
            final_message = message

            if template_code:
                tpl = NotificationTemplate.objects.filter(code=template_code, channel=ch, is_active=True).first()
                if tpl:
                    try:
                        final_title = tpl.subject or title
                        final_message = tpl.body_template.format(**context)
                    except Exception as e:
                        logger.warning(f"Failed formatting template {template_code}: {e}; using fallback.")

            # Create notification record
            recipient_phone = member.phone_number or (member.user.phone_number if member.user else "")
            recipient_email = member.email or (member.user.email if member.user else "")

            # Guard against missing recipient info
            if ch in [NotificationChannel.SMS, NotificationChannel.WHATSAPP] and not recipient_phone:
                logger.warning(f"No phone number for member {member.membership_number}; skipping {ch}")
                continue
            if ch == NotificationChannel.EMAIL and not recipient_email:
                logger.warning(f"No email for member {member.membership_number}; skipping {ch}")
                continue

            notif = Notification.objects.create(
                recipient_member=member,
                recipient_user=member.user,
                recipient_phone=recipient_phone,
                recipient_email=recipient_email,
                channel=ch,
                category=category,
                title=final_title,
                message=final_message,
                status=NotificationStatus.QUEUED,
                delivery_attempts=1,
            )

            # Invoke adapter
            adapter_class = cls.ADAPTER_MAP.get(ch)
            if not adapter_class:
                notif.status = NotificationStatus.FAILED
                notif.error_message = f"No adapter registered for channel {ch}"
                notif.save(update_fields=['status', 'error_message'])
                continue

            adapter = adapter_class()
            recipient_target = (
                recipient_phone if ch in [NotificationChannel.SMS, NotificationChannel.WHATSAPP]
                else recipient_email if ch == NotificationChannel.EMAIL
                else (member.user.username if member.user else str(member.id))
            )

            res = adapter.send(recipient_target, final_title, final_message, context)

            # Update notification status
            notif.status = res.get('status', NotificationStatus.FAILED)
            notif.external_id = res.get('external_id', '')
            notif.error_message = res.get('error_message', '')
            if res.get('success'):
                notif.sent_at = timezone.now()
                if ch == NotificationChannel.IN_APP:
                    notif.delivered_at = timezone.now()
            notif.save()

            # Record log
            NotificationLog.objects.create(
                notification=notif,
                attempt_number=1,
                status=notif.status,
                provider_response=res.get('raw_response', '')
            )

            created_notifications.append(notif)

        return created_notifications

    @classmethod
    def broadcast_announcement(cls, announcement: Announcement) -> int:
        """
        Dispatches announcement in-app and via SMS to all active SACCO members.
        """
        from nht_sacco.apps.members.models import Member, MembershipStatus
        active_members = Member.objects.filter(status=MembershipStatus.ACTIVE).select_related('user')
        count = 0
        for m in active_members:
            cls.dispatch_to_member(
                member=m,
                category=NotificationCategory.ANNOUNCEMENT,
                title=f"Announcement: {announcement.title}",
                message=announcement.content,
                channels=[NotificationChannel.IN_APP]
            )
            count += 1
        return count
