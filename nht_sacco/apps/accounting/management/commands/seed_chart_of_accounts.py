from datetime import date
from django.core.management.base import BaseCommand
from nht_sacco.apps.accounting.models import Account, AccountType, FinancialPeriod

class Command(BaseCommand):
    help = 'Seeds the standard SACCO Chart of Accounts and initial Financial Period.'

    def handle(self, *args, **options):
        # 1. Seed Financial Period
        period, p_created = FinancialPeriod.objects.get_or_create(
            name='FY2026-Q4',
            defaults={
                'start_date': date(2026, 10, 1),
                'end_date': date(2026, 12, 31),
                'is_closed': False,
            }
        )
        if p_created:
            self.stdout.write(self.style.SUCCESS(f"Created Financial Period: {period.name}"))
        else:
            self.stdout.write(f"Period already exists: {period.name}")

        # 2. Seed Standard Chart of Accounts
        accounts = [
            {'code': '1010', 'name': 'Office Petty Cash', 'type': AccountType.ASSET, 'description': 'Cash in SACCO office vault'},
            {'code': '1020', 'name': 'Safaricom M-Pesa PayBill Account', 'type': AccountType.ASSET, 'description': 'Collections in Daraja PayBill'},
            {'code': '1030', 'name': 'Equity Bank Main Operations Account', 'type': AccountType.ASSET, 'description': 'Main SACCO commercial bank account'},
            {'code': '1100', 'name': 'Accounts Receivable - Members', 'type': AccountType.ASSET, 'description': 'Outstanding unpaid invoice balances'},
            {'code': '2010', 'name': 'Member Deposit Advances', 'type': AccountType.LIABILITY, 'description': 'Prepaid funds credited to members'},
            {'code': '2020', 'name': 'Statutory Pass-Through Payable', 'type': AccountType.LIABILITY, 'description': 'Funds collected for KeNHA/NTSA/Insurance pending remittance'},
            {'code': '3010', 'name': 'Member Share Capital', 'type': AccountType.EQUITY, 'description': 'Core member equity contributions'},
            {'code': '3020', 'name': 'Retained Operating Surplus', 'type': AccountType.EQUITY, 'description': 'Accumulated SACCO operating balance'},
            {'code': '4010', 'name': 'Membership Admission Fee Revenue', 'type': AccountType.REVENUE, 'description': 'New member onboarding income'},
            {'code': '4020', 'name': 'Monthly Fleet Operations Levy', 'type': AccountType.REVENUE, 'description': 'Recurring monthly vehicle operations subscriptions'},
            {'code': '4030', 'name': 'Document Renewal Processing Income', 'type': AccountType.REVENUE, 'description': 'Secretariat handling fee for permits and licenses'},
            {'code': '5010', 'name': 'Office Administration & Utilities', 'type': AccountType.EXPENSE, 'description': 'Stationery, internet, rent, utilities'},
            {'code': '5020', 'name': 'Regulatory Compliance & Legal', 'type': AccountType.EXPENSE, 'description': 'Legal representation, auditing, regulatory liaison'},
            {'code': '5030', 'name': 'Member & Crew Welfare Relief', 'type': AccountType.EXPENSE, 'description': 'Emergency relief and crew bereavement grants'},
        ]

        for acc_data in accounts:
            acc, created = Account.objects.get_or_create(
                code=acc_data['code'],
                defaults=acc_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created GL Account: {acc.code} - {acc.name} ({acc.get_type_display()})"))
            else:
                self.stdout.write(f"Account exists: {acc.code}")
