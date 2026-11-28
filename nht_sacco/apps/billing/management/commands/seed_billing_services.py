from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from nht_sacco.apps.billing.models import ServiceItem, ServicePrice, ServiceCategory

class Command(BaseCommand):
    help = 'Seeds SACCO service catalogue items and pricing schedules for NHT-SMS.'

    def handle(self, *args, **options):
        services = [
            {
                'code': 'MEM_REG_FEE',
                'name': 'New Member Registration & Onboarding',
                'category': ServiceCategory.MEMBERSHIP,
                'is_statutory': False,
                'amount': Decimal('5000.00'),
                'description': 'One-time registration fee for new SACCO members.'
            },
            {
                'code': 'VEH_REG_FEE',
                'name': 'Vehicle Fleet Induction & Staging Fee',
                'category': ServiceCategory.MEMBERSHIP,
                'is_statutory': False,
                'amount': Decimal('10000.00'),
                'description': 'One-time vehicle registration fee for admission to SACCO routes.'
            },
            {
                'code': 'MONTHLY_SUB_LIGHT',
                'name': 'Monthly SACCO Operations Levy (Light Commercial Truck)',
                'category': ServiceCategory.SUBSCRIPTION,
                'is_statutory': False,
                'amount': Decimal('2500.00'),
                'description': 'Monthly operational subscription fee for light commercial trucks and courier vans.'
            },
            {
                'code': 'MONTHLY_SUB_MEDIUM',
                'name': 'Monthly SACCO Operations Levy (Medium Commercial Truck)',
                'category': ServiceCategory.SUBSCRIPTION,
                'is_statutory': False,
                'amount': Decimal('3500.00'),
                'description': 'Monthly operational subscription fee for medium commercial trucks (8–15 tonnes).'
            },
            {
                'code': 'MONTHLY_SUB_HEAVY',
                'name': 'Monthly SACCO Operations Levy (Heavy Truck / Prime Mover & Trailer)',
                'category': ServiceCategory.SUBSCRIPTION,
                'is_statutory': False,
                'amount': Decimal('5000.00'),
                'description': 'Monthly operational subscription fee for heavy commercial trucks, prime movers, tankers, and trailers.'
            },
            {
                'code': 'RENEWAL_FEE',
                'name': 'Document Renewal Secretariat Processing Fee',
                'category': ServiceCategory.RENEWAL,
                'is_statutory': False,
                'amount': Decimal('1000.00'),
                'description': 'Administrative handling fee for regulatory document renewals.'
            },
            {
                'code': 'STAT_KENHA_PERMIT',
                'name': 'KeNHA Corridor Authority Road Permit',
                'category': ServiceCategory.STATUTORY,
                'is_statutory': True,
                'amount': Decimal('4500.00'),
                'description': 'Statutory pass-through government permit for corridor operations.'
            },
            {
                'code': 'STAT_NTSA_RSL',
                'name': 'NTSA Road Service Licence (RSL)',
                'category': ServiceCategory.STATUTORY,
                'is_statutory': True,
                'amount': Decimal('3750.00'),
                'description': 'Statutory pass-through fee for NTSA commercial freight road service license.'
            },
            {
                'code': 'WELFARE_LEVY',
                'name': 'Drivers & Crew Welfare / Emergency Fund',
                'category': ServiceCategory.LEVY,
                'is_statutory': False,
                'amount': Decimal('500.00'),
                'description': 'Monthly member contribution to driver medical & emergency relief.'
            },
        ]

        today = timezone.now().date()

        for s in services:
            amount = s.pop('amount')
            item, created = ServiceItem.objects.get_or_create(
                code=s['code'],
                defaults=s
            )
            # Create or update price tier
            price = ServicePrice.objects.filter(service_item=item, effective_to__isnull=True).first()
            if not price:
                ServicePrice.objects.create(
                    service_item=item,
                    amount=amount,
                    effective_from=today
                )
                self.stdout.write(self.style.SUCCESS(f"Created Service: {item.code} at KES {amount}"))
            else:
                self.stdout.write(f"Service already priced: {item.code}")
