"""
Celery background tasks for member management and statements.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from .models import Member, MembershipStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus
from nht_sacco.apps.notifications.services import NotificationDispatcherService
from nht_sacco.apps.notifications.models import NotificationCategory

logger = logging.getLogger(__name__)


def task_monthly_member_statements():
    """
    Computes monthly running statement summaries for all active SACCO members
    and dispatches summary notifications.
    """
    active_members = Member.objects.filter(status=MembershipStatus.ACTIVE)
    summaries_processed = 0

    for member in active_members:
        invoices = member.invoices.all()
        total_invoiced = sum((inv.total_amount for inv in invoices), Decimal('0.00'))

        payments = Payment.objects.filter(
            invoice__member=member,
            status=PaymentStatus.SUCCESS
        )
        total_paid = sum((p.amount for p in payments), Decimal('0.00'))
        outstanding_balance = total_invoiced - total_paid

        # Dispatch summary notification if there is an active balance
        if outstanding_balance > Decimal('0.00'):
            message = (
                f"Hello {member.full_name}, your SACCO account balance for the current period is "
                f"KES {outstanding_balance:,.2f}. Total invoiced: KES {total_invoiced:,.2f}, "
                f"Total paid: KES {total_paid:,.2f}. View full statement on the member portal."
            )
            try:
                NotificationDispatcherService.dispatch_to_member(
                    member=member,
                    category=NotificationCategory.BILLING,
                    title="Monthly Statement Summary",
                    message=message,
                    context={
                        'total_invoiced': str(total_invoiced),
                        'total_paid': str(total_paid),
                        'outstanding_balance': str(outstanding_balance),
                    }
                )
            except Exception as exc:
                logger.error(f"Failed to dispatch monthly statement to {member.membership_number}: {exc}")

        summaries_processed += 1

    logger.info(f"Monthly statement task completed. Processed {summaries_processed} active members.")
    return {'members_processed': summaries_processed}


try:
    from celery import shared_task
    task_monthly_member_statements = shared_task(name='nht_sacco.apps.members.tasks.task_monthly_member_statements')(task_monthly_member_statements)
except ImportError:
    pass
