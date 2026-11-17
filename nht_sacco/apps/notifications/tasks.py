"""
Celery background tasks for multi-channel notification processing and retry queues.
"""

import logging
from django.utils import timezone
from .models import Notification, NotificationStatus, NotificationLog
from .services import NotificationDispatcherService

logger = logging.getLogger(__name__)


def task_retry_failed_notifications():
    """
    Retries failed notifications that have attempted fewer than 3 deliveries.
    """
    failed_notifs = Notification.objects.filter(
        status=NotificationStatus.FAILED,
        delivery_attempts__lt=3
    )[:50]

    retried_count = 0
    success_count = 0

    for notif in failed_notifs:
        adapter_class = NotificationDispatcherService.ADAPTER_MAP.get(notif.channel)
        if not adapter_class:
            continue

        notif.delivery_attempts += 1
        adapter = adapter_class()
        recipient_target = notif.recipient_phone or notif.recipient_email or (notif.recipient_user.username if notif.recipient_user else "")

        try:
            res = adapter.send(recipient_target, notif.title, notif.message, {})
            notif.status = res.get('status', NotificationStatus.FAILED)
            notif.external_id = res.get('external_id', notif.external_id)
            notif.error_message = res.get('error_message', '')
            if res.get('success'):
                notif.sent_at = timezone.now()
                success_count += 1
            notif.save(update_fields=['delivery_attempts', 'status', 'external_id', 'error_message', 'sent_at'])

            NotificationLog.objects.create(
                notification=notif,
                attempt_number=notif.delivery_attempts,
                status=notif.status,
                provider_response=res.get('raw_response', '')
            )
            retried_count += 1
        except Exception as exc:
            logger.error(f"Error retrying notification {notif.id}: {exc}")

    logger.info(f"Notification retry task completed. Retried: {retried_count}, Succeeded: {success_count}")
    return {'retried_count': retried_count, 'success_count': success_count}


try:
    from celery import shared_task
    task_retry_failed_notifications = shared_task(name='nht_sacco.apps.notifications.tasks.task_retry_failed_notifications')(task_retry_failed_notifications)
except ImportError:
    pass
