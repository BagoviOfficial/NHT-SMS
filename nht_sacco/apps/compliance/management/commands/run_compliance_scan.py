"""
Management command to run the compliance scan manually or via cron.
"""

from django.core.management.base import BaseCommand
from nht_sacco.apps.compliance.tasks import task_daily_compliance_scan


class Command(BaseCommand):
    help = 'Executes the daily fleet compliance and document expiry scan'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initiating fleet regulatory compliance scan..."))
        result = task_daily_compliance_scan()
        self.stdout.write(
            self.style.SUCCESS(
                f"Compliance scan completed successfully. Alerts generated: {result.get('alerts_created', 0)}, "
                f"Non-compliant vehicles: {result.get('non_compliant_count', 0)}"
            )
        )
