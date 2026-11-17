from django.core.management.base import BaseCommand
from nht_sacco.apps.notifications.models import NotificationTemplate, NotificationChannel


class Command(BaseCommand):
    help = "Seed default communication notification templates"

    def handle(self, *args, **options):
        templates = [
            {
                'code': 'COMPLIANCE_EXPIRING_30D_SMS',
                'name': 'Vehicle Document Expiry Reminder (SMS)',
                'channel': NotificationChannel.SMS,
                'subject': '',
                'body_template': 'NHT SACCO: Warning! Permit {doc_type} for vehicle {vehicle_plate} expires on {expiry_date}. Please renew via member portal or contact the renewal desk.',
            },
            {
                'code': 'COMPLIANCE_EXPIRING_30D_EMAIL',
                'name': 'Vehicle Document Expiry Reminder (Email)',
                'channel': NotificationChannel.EMAIL,
                'subject': 'Urgent: {doc_type} Expiring Soon for Vehicle {vehicle_plate}',
                'body_template': 'Dear {member_name},\n\nPlease be advised that the regulatory permit {doc_type} for your vehicle {vehicle_plate} expires on {expiry_date}.\n\nTo prevent compliance sanctions or impoundment, please submit your renewal request online via the NHT Member Portal.\n\nNorthern Highways Transporters SACCO Compliance Desk',
            },
            {
                'code': 'INVOICE_ISSUED_SMS',
                'name': 'Invoice Issued Alert (SMS)',
                'channel': NotificationChannel.SMS,
                'subject': '',
                'body_template': 'NHT SACCO: New invoice {invoice_number} for KES {amount} has been generated. Log into the portal to pay via M-Pesa or bank slip.',
            },
            {
                'code': 'PAYMENT_RECEIVED_SMS',
                'name': 'Payment Confirmation Alert (SMS)',
                'channel': NotificationChannel.SMS,
                'subject': '',
                'body_template': 'NHT SACCO: Payment received! Receipt {receipt_number} for KES {amount} cleared. Outstanding balance: KES {balance_due}. Thank you.',
            },
            {
                'code': 'RENEWAL_STATUS_UPDATE_SMS',
                'name': 'Renewal Status Notification (SMS)',
                'channel': NotificationChannel.SMS,
                'subject': '',
                'body_template': 'NHT SACCO: Renewal request {request_number} for vehicle {vehicle_plate} updated to: {status}.',
            },
        ]

        count = 0
        for tpl_data in templates:
            tpl, created = NotificationTemplate.objects.get_or_create(
                code=tpl_data['code'],
                defaults=tpl_data
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f"Created template: {tpl.code}"))
            else:
                self.stdout.write(self.style.WARNING(f"Template already exists: {tpl.code}"))

        self.stdout.write(self.style.SUCCESS(f"Finished seeding templates. {count} new templates created."))
