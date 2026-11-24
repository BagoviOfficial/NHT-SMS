from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial administrative and departmental staff accounts for NHT-SMS.'

    def handle(self, *args, **options):
        staff_accounts = [
            {
                'username': 'admin',
                'email': 'admin@nhttransporters.co.ke',
                'password': 'Admin@NHT2026!',
                'role': UserRole.SUPER_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'SACCO',
                'last_name': 'Administrator',
                'phone_number': '+254700000001',
                'national_id': '10000001',
            },
            {
                'username': 'chairman',
                'email': 'chairman@nhttransporters.co.ke',
                'password': 'Chairman@NHT2026!',
                'role': UserRole.CHAIRMAN,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Abdirahman',
                'last_name': 'Warsame',
                'phone_number': '+254700000006',
                'national_id': '10000006',
            },
            {
                'username': 'secretary',
                'email': 'secretary@nhttransporters.co.ke',
                'password': 'Secretary@NHT2026!',
                'role': UserRole.SECRETARY,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Ahmed',
                'last_name': 'Ibrahim',
                'phone_number': '+254700000002',
                'national_id': '10000002',
            },
            {
                'username': 'treasurer',
                'email': 'treasurer@nhttransporters.co.ke',
                'password': 'Treasurer@NHT2026!',
                'role': UserRole.TREASURER,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Fatuma',
                'last_name': 'Mohamed',
                'phone_number': '+254700000003',
                'national_id': '10000003',
            },
            {
                'username': 'accountant',
                'email': 'accountant@nhttransporters.co.ke',
                'password': 'Accountant@NHT2026!',
                'role': UserRole.ACCOUNTANT,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Amina',
                'last_name': 'Farah',
                'phone_number': '+254700000007',
                'national_id': '10000007',
            },
            {
                'username': 'compliance',
                'email': 'compliance@nhttransporters.co.ke',
                'password': 'Compliance@NHT2026!',
                'role': UserRole.COMPLIANCE_OFFICER,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Hassan',
                'last_name': 'Ali',
                'phone_number': '+254700000004',
                'national_id': '10000004',
            },
            {
                'username': 'renewal_officer',
                'email': 'renewals@nhttransporters.co.ke',
                'password': 'Renewals@NHT2026!',
                'role': UserRole.RENEWAL_OFFICER,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Salim',
                'last_name': 'Borow',
                'phone_number': '+254700000008',
                'national_id': '10000008',
            },
            {
                'username': 'field_officer',
                'email': 'field@nhttransporters.co.ke',
                'password': 'Field@NHT2026!',
                'role': UserRole.FIELD_OFFICER,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Ibrahim',
                'last_name': 'Duba',
                'phone_number': '+254700000009',
                'national_id': '10000009',
            },
            {
                'username': 'auditor',
                'email': 'auditor@nhttransporters.co.ke',
                'password': 'Auditor@NHT2026!',
                'role': UserRole.AUDITOR,
                'is_staff': True,
                'is_superuser': False,
                'first_name': 'Zainab',
                'last_name': 'Omar',
                'phone_number': '+254700000005',
                'national_id': '10000005',
            },
        ]

        for acc in staff_accounts:
            user, created = User.objects.get_or_create(
                username=acc['username'],
                defaults={
                    'email': acc['email'],
                    'role': acc['role'],
                    'is_staff': acc['is_staff'],
                    'is_superuser': acc['is_superuser'],
                    'first_name': acc['first_name'],
                    'last_name': acc['last_name'],
                    'phone_number': acc['phone_number'],
                    'national_id': acc['national_id'],
                    'is_verified': True,
                }
            )
            if created:
                user.set_password(acc['password'])
                user.save()
                AuditLog.objects.create(
                    action=AuditAction.CREATE,
                    entity_type='User',
                    entity_id=str(user.pk),
                    actor_username='SYSTEM',
                    outcome=AuditOutcome.SUCCESS,
                    change_details={'username': user.username, 'role': user.role}
                )
                self.stdout.write(self.style.SUCCESS(f"Created staff account: {user.username} ({user.get_role_display()})"))
            else:
                self.stdout.write(f"Account already exists: {user.username}")
