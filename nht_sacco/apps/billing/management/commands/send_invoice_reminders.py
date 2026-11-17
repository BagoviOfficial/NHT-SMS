"""
Management command to run overdue invoice reminders manually or via cron.
"""

from django.core.management.base import BaseCommand
from nht_sacco.apps.billing.tasks import task_overdue_invoice_reminders


class Command(BaseCommand):
    help = 'Scans for overdue invoices and dispatches payment reminders to members'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initiating overdue invoice reminder scan..."))
        result = task_overdue_invoice_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed. Overdue invoices found: {result.get('overdue_count', 0)}, "
                f"Reminders dispatched: {result.get('reminders_sent', 0)}"
            )
        )
