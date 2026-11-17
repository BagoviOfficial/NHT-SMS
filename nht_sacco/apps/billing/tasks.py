"""
Celery background tasks for billing and invoice management.
"""

import logging
from django.utils import timezone
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.notifications.services import NotificationDispatcherService
from nht_sacco.apps.notifications.models import NotificationCategory

logger = logging.getLogger(__name__)


def task_overdue_invoice_reminders():
    """
    Identifies unpaid or partially paid invoices that are past due date
    and dispatches reminder notifications to members.
    """
    today = timezone.now().date()
    overdue_invoices = Invoice.objects.filter(
        status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID],
        due_date__lt=today
    ).select_related('member')

    reminders_sent = 0
    for invoice in overdue_invoices:
        days_overdue = (today - invoice.due_date).days
        message = (
            f"Dear {invoice.member.full_name}, your invoice {invoice.invoice_number} "
            f"for KES {invoice.balance_due:,.2f} is overdue by {days_overdue} days. "
            f"Please settle via M-Pesa or contact the SACCO office."
        )
        try:
            NotificationDispatcherService.dispatch_to_member(
                member=invoice.member,
                category=NotificationCategory.BILLING,
                title="Overdue Invoice Notice",
                message=message,
                context={
                    'invoice_number': invoice.invoice_number,
                    'balance_due': str(invoice.balance_due),
                    'days_overdue': days_overdue,
                }
            )
            reminders_sent += 1
        except Exception as exc:
            logger.error(f"Failed to dispatch reminder for invoice {invoice.invoice_number}: {exc}")

    logger.info(f"Overdue invoice reminder task completed. Reminders sent: {reminders_sent}")
    return {'overdue_count': overdue_invoices.count(), 'reminders_sent': reminders_sent}


try:
    from celery import shared_task
    task_overdue_invoice_reminders = shared_task(name='nht_sacco.apps.billing.tasks.task_overdue_invoice_reminders')(task_overdue_invoice_reminders)
except ImportError:
    pass
