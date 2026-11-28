from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, VehicleStatus, FuelType
from nht_sacco.apps.drivers.models import Driver, DriverAssignment, DriverStatus
from nht_sacco.apps.routes.models import Route, VehicleRouteAssignment

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds sample SACCO members, fleet vehicles, drivers, and routes for NHT-SMS.'

    def handle(self, *args, **options):
        admin_user = User.objects.filter(role=UserRole.SUPER_ADMIN).first()

        # Seed Member 1
        u1, _ = User.objects.get_or_create(
            username='alihassan',
            defaults={
                'email': 'ali.hassan@example.com',
                'role': UserRole.MEMBER,
                'first_name': 'Ali',
                'last_name': 'Hassan',
                'phone_number': '+254711111111',
                'national_id': '22114455',
            }
        )
        if _:
            u1.set_password('Member@NHT2026!')
            u1.save()

        m1, _ = Member.objects.get_or_create(
            user=u1,
            defaults={
                'membership_number': 'NHT-MBR-2026-0001',
                'first_name': 'Ali',
                'last_name': 'Hassan',
                'national_id': '22114455',
                'phone_number': '+254711111111',
                'email': 'ali.hassan@example.com',
                'category': MembershipCategory.INDIVIDUAL_OPERATOR,
                'status': MembershipStatus.ACTIVE,
                'county': 'Isiolo',
                'next_of_kin_name': 'Fatuma Hassan',
                'next_of_kin_relation': 'Spouse',
                'next_of_kin_phone': '+254711111112',
                'approved_by': admin_user,
            }
        )

        # Seed Member 2
        u2, _ = User.objects.get_or_create(
            username='halimabdi',
            defaults={
                'email': 'halima.abdi@example.com',
                'role': UserRole.MEMBER,
                'first_name': 'Halima',
                'last_name': 'Abdi',
                'phone_number': '+254722222222',
                'national_id': '22334455',
            }
        )
        if _:
            u2.set_password('Member@NHT2026!')
            u2.save()

        m2, _ = Member.objects.get_or_create(
            user=u2,
            defaults={
                'membership_number': 'NHT-MBR-2026-0002',
                'first_name': 'Halima',
                'last_name': 'Abdi',
                'national_id': '22334455',
                'phone_number': '+254722222222',
                'email': 'halima.abdi@example.com',
                'category': MembershipCategory.FLEET_OWNER,
                'status': MembershipStatus.ACTIVE,
                'county': 'Moyale',
                'next_of_kin_name': 'Abdi Nur',
                'next_of_kin_relation': 'Brother',
                'next_of_kin_phone': '+254722222223',
                'approved_by': admin_user,
            }
        )

        # Seed Commercial Trucks & Trailers for Member 1
        v1, _ = Vehicle.objects.get_or_create(
            registration_number='KDA 101A',
            defaults={
                'chassis_number': 'CHS-ISUZU-101A',
                'engine_number': 'ENG-4HK1-101A',
                'make': 'Isuzu',
                'model': 'FRR 90 Cargo Truck',
                'year_of_manufacture': 2021,
                'category': VehicleCategory.MEDIUM_TRUCK,
                'fuel_type': FuelType.DIESEL,
                'carrying_capacity': 10,
                'color': 'White with Navy & Orange Stripes',
                'current_owner': m1,
                'status': VehicleStatus.ACTIVE,
                'created_by': admin_user,
            }
        )

        v2, _ = Vehicle.objects.get_or_create(
            registration_number='KDC 202B',
            defaults={
                'chassis_number': 'CHS-ACTROS-202B',
                'engine_number': 'ENG-OM471-202B',
                'make': 'Mercedes-Benz',
                'model': 'Actros 2645 Prime Mover',
                'year_of_manufacture': 2022,
                'category': VehicleCategory.PRIME_MOVER,
                'fuel_type': FuelType.DIESEL,
                'carrying_capacity': 28,
                'color': 'White with Navy Stripes',
                'current_owner': m1,
                'status': VehicleStatus.ACTIVE,
                'created_by': admin_user,
            }
        )

        # Seed Prime Mover & Semi-Trailer for Member 2
        v3, _ = Vehicle.objects.get_or_create(
            registration_number='KDB 303C',
            defaults={
                'chassis_number': 'CHS-SCANIA-303C',
                'engine_number': 'ENG-DC13-303C',
                'make': 'Scania',
                'model': 'R450 Heavy Truck',
                'year_of_manufacture': 2023,
                'category': VehicleCategory.HEAVY_TRUCK,
                'fuel_type': FuelType.DIESEL,
                'carrying_capacity': 25,
                'color': 'White with Full SACCO Livery',
                'current_owner': m2,
                'status': VehicleStatus.ACTIVE,
                'created_by': admin_user,
            }
        )

        v4, _ = Vehicle.objects.get_or_create(
            registration_number='ZA 4012',
            defaults={
                'chassis_number': 'CHS-TRL-4012',
                'engine_number': None,
                'make': 'CIM',
                'model': '40ft Tri-Axle Flatbed Trailer',
                'year_of_manufacture': 2023,
                'category': VehicleCategory.SEMI_TRAILER,
                'fuel_type': FuelType.NONE,
                'carrying_capacity': 32,
                'color': 'White with SACCO Stripes',
                'current_owner': m2,
                'status': VehicleStatus.ACTIVE,
                'created_by': admin_user,
            }
        )

        # Seed Drivers & Driver Portal User
        du1, du1_created = User.objects.get_or_create(
            username='yusufjama',
            defaults={
                'email': 'yusuf.jama@example.com',
                'role': UserRole.DRIVER,
                'first_name': 'Yusuf',
                'last_name': 'Jama',
                'phone_number': '+254733333331',
                'national_id': '30112233',
                'is_verified': True,
            }
        )
        if du1_created:
            du1.set_password('Driver@NHT2026!')
            du1.save()

        today = date.today()
        d1, _ = Driver.objects.get_or_create(
            national_id='30112233',
            defaults={
                'user': du1,
                'full_name': 'Yusuf Jama',
                'phone_number': '+254733333331',
                'driving_license_number': 'DL-NTSA-1001',
                'dl_expiry_date': today + timedelta(days=365),
                'psv_badge_number': 'COM-2026-001',
                'psv_badge_expiry': today + timedelta(days=365),
                'emergency_contact_name': 'Amina Jama',
                'emergency_contact_phone': '+254733333332',
                'status': DriverStatus.ACTIVE,
            }
        )
        if not d1.user:
            d1.user = du1
            d1.save(update_fields=['user'])
        DriverAssignment.objects.get_or_create(
            driver=d1,
            vehicle=v1,
            defaults={'is_current': True, 'assigned_by': admin_user}
        )

        d2, _ = Driver.objects.get_or_create(
            national_id='30223344',
            defaults={
                'full_name': 'Peter Mwangi',
                'phone_number': '+254744444441',
                'driving_license_number': 'DL-NTSA-1002',
                'dl_expiry_date': today + timedelta(days=200),
                'psv_badge_number': 'COM-2026-002',
                'psv_badge_expiry': today + timedelta(days=200),
                'emergency_contact_name': 'Grace Wanjiku',
                'emergency_contact_phone': '+254744444442',
                'status': DriverStatus.ACTIVE,
            }
        )
        DriverAssignment.objects.get_or_create(
            driver=d2,
            vehicle=v3,
            defaults={'is_current': True, 'assigned_by': admin_user}
        )

        # Seed Routes
        r1, _ = Route.objects.get_or_create(
            route_code='NHT-R01',
            defaults={
                'name': 'Northern Corridor Express',
                'origin': 'Nairobi (Country Bus / Tea Room)',
                'destination': 'Moyale Border Post',
                'distance_km': Decimal('775.50'),
                'intermediate_stops': ['Thika', 'Nanyuki', 'Isiolo', 'Archer\'s Post', 'Laisamis', 'Marsabit', 'Turbi'],
                'is_active': True,
            }
        )

        r2, _ = Route.objects.get_or_create(
            route_code='NHT-R02',
            defaults={
                'name': 'Upper Eastern Shuttle',
                'origin': 'Nairobi',
                'destination': 'Maua / Meru',
                'distance_km': Decimal('290.00'),
                'intermediate_stops': ['Thika', 'Kenol', 'Makutano', 'Embu', 'Chuka', 'Nkubu', 'Meru'],
                'is_active': True,
            }
        )

        # Assign vehicles to routes
        VehicleRouteAssignment.objects.get_or_create(
            vehicle=v1,
            route=r2,
            defaults={'road_service_license': 'RSL-NTSA-2026-0101', 'is_active': True, 'authorized_by': admin_user}
        )
        VehicleRouteAssignment.objects.get_or_create(
            vehicle=v3,
            route=r1,
            defaults={'road_service_license': 'RSL-NTSA-2026-0303', 'is_active': True, 'authorized_by': admin_user}
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded SACCO Members, Vehicles, Drivers, and Routes."))
