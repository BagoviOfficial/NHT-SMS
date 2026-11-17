from django.core.management.base import BaseCommand
from nht_sacco.apps.documents.models import DocumentType, DocumentCategory

class Command(BaseCommand):
    help = 'Seeds mandatory Kenyan transport regulatory document types for NHT-SMS.'

    def handle(self, *args, **options):
        types_data = [
            {
                'name': 'Motor Vehicle Inspection Certificate',
                'category': DocumentCategory.INSPECTION,
                'standard_validity_months': 6,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'PSV Commercial Insurance Certificate',
                'category': DocumentCategory.INSURANCE,
                'standard_validity_months': 12,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'NTSA Road Service Licence (RSL)',
                'category': DocumentCategory.NTSA_RSL,
                'standard_validity_months': 12,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'KeNHA Corridor Route Permit',
                'category': DocumentCategory.KENHA_PERMIT,
                'standard_validity_months': 12,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'Speed Governor Calibration Certificate',
                'category': DocumentCategory.SPEED_GOVERNOR,
                'standard_validity_months': 12,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'County Transport Business Permit',
                'category': DocumentCategory.COUNTY_PERMIT,
                'standard_validity_months': 12,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': True,
                'is_mandatory_for_driver': False,
            },
            {
                'name': 'Driving License PSV Endorsement',
                'category': DocumentCategory.DRIVER_LICENSE,
                'standard_validity_months': 36,
                'reminder_thresholds': [30, 14, 7, 3, 0],
                'is_mandatory_for_vehicle': False,
                'is_mandatory_for_driver': True,
            },
        ]

        for item in types_data:
            dt, created = DocumentType.objects.get_or_create(
                name=item['name'],
                defaults=item
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Document Type: {dt.name}"))
            else:
                self.stdout.write(f"Document Type already exists: {dt.name}")
