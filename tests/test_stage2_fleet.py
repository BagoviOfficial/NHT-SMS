import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, VehicleStatus, FuelType, VehicleOwnershipHistory
from nht_sacco.apps.drivers.models import Driver, DriverAssignment, DriverStatus
from nht_sacco.apps.routes.models import Route, VehicleRouteAssignment

User = get_user_model()

@pytest.fixture
def sacco_admin(db):
    return User.objects.create_user(
        username='fleet_admin',
        email='fleetadmin@nhttransporters.co.ke',
        password='AdminPassword123!',
        role=UserRole.SUPER_ADMIN
    )

@pytest.fixture
def sample_member(db, sacco_admin):
    user = User.objects.create_user(
        username='fleet_owner_1',
        email='owner1@nhttransporters.co.ke',
        password='OwnerPassword123!',
        role=UserRole.MEMBER
    )
    return Member.objects.create(
        user=user,
        membership_number='NHT-MBR-2026-9001',
        first_name='Kassim',
        last_name='Roble',
        national_id='99887766',
        phone_number='+254799887766',
        email='owner1@nhttransporters.co.ke',
        category=MembershipCategory.FLEET_OWNER,
        status=MembershipStatus.PENDING,
        next_of_kin_name='Amina Roble',
        next_of_kin_relation='Daughter',
        next_of_kin_phone='+254799887767'
    )

@pytest.mark.django_db
class TestMemberManagement:
    def test_member_approval_and_suspension(self, sample_member, sacco_admin):
        assert sample_member.status == MembershipStatus.PENDING
        sample_member.approve(sacco_admin, notes='Vetted by Secretariat')
        assert sample_member.status == MembershipStatus.ACTIVE
        assert sample_member.approved_by == sacco_admin

        sample_member.suspend(sacco_admin, reason='Pending annual renewal')
        assert sample_member.status == MembershipStatus.SUSPENDED

        sample_member.reinstate(sacco_admin)
        assert sample_member.status == MembershipStatus.ACTIVE

    def test_duplicate_membership_number_rejected(self, sample_member):
        user2 = User.objects.create_user(
            username='user_dup',
            email='dup@nhttransporters.co.ke',
            password='Password123!',
            role=UserRole.MEMBER
        )
        with pytest.raises(IntegrityError):
            Member.objects.create(
                user=user2,
                membership_number='NHT-MBR-2026-9001',  # duplicate
                first_name='Duplicate',
                last_name='Test',
                national_id='99887760',
                phone_number='+254799887760',
                email='dup@nhttransporters.co.ke',
                category=MembershipCategory.INDIVIDUAL_OPERATOR,
                next_of_kin_name='Kin',
                next_of_kin_relation='Friend',
                next_of_kin_phone='+254799887761'
            )


@pytest.mark.django_db
class TestVehicleManagement:
    def test_vehicle_registration_and_multi_ownership(self, sample_member, sacco_admin):
        # Register first vehicle (lowercase plate tests uppercase normalization)
        v1 = Vehicle.objects.create(
            registration_number='kda 888x',
            chassis_number='CHS-KDA888X',
            engine_number='ENG-KDA888X',
            make='Toyota',
            model='HiAce',
            year_of_manufacture=2020,
            category=VehicleCategory.MATATU_14,
            carrying_capacity=14,
            current_owner=sample_member,
            created_by=sacco_admin
        )
        assert v1.registration_number == 'KDA 888X'
        assert v1.qr_token is not None

        # Register second vehicle for same member (Fleet Owner)
        v2 = Vehicle.objects.create(
            registration_number='KDC 999Y',
            chassis_number='CHS-KDC999Y',
            engine_number='ENG-KDC999Y',
            make='Isuzu',
            model='FRR',
            year_of_manufacture=2022,
            category=VehicleCategory.MINIBUS_33,
            carrying_capacity=33,
            current_owner=sample_member,
            created_by=sacco_admin
        )
        assert sample_member.vehicles.count() == 2

    def test_ownership_transfer(self, sample_member, sacco_admin):
        v = Vehicle.objects.create(
            registration_number='KDB 777Z',
            chassis_number='CHS-KDB777Z',
            engine_number='ENG-KDB777Z',
            make='Scania',
            model='F310',
            year_of_manufacture=2023,
            category=VehicleCategory.BUS_50_PLUS,
            carrying_capacity=50,
            current_owner=sample_member,
            created_by=sacco_admin
        )

        user_buyer = User.objects.create_user(
            username='buyer_member',
            email='buyer@nhttransporters.co.ke',
            password='BuyerPassword123!',
            role=UserRole.MEMBER
        )
        buyer_member = Member.objects.create(
            user=user_buyer,
            membership_number='NHT-MBR-2026-9002',
            first_name='Abdirahman',
            last_name='Warsame',
            national_id='88776655',
            phone_number='+254788776655',
            email='buyer@nhttransporters.co.ke',
            category=MembershipCategory.INDIVIDUAL_OPERATOR,
            next_of_kin_name='Halima Warsame',
            next_of_kin_relation='Sister',
            next_of_kin_phone='+254788776656'
        )

        # Record transfer
        transfer = VehicleOwnershipHistory.objects.create(
            vehicle=v,
            previous_owner=sample_member,
            new_owner=buyer_member,
            transfer_reason='Direct private sale and registration endorsement.',
            authorized_by=sacco_admin
        )
        v.current_owner = buyer_member
        v.save()

        assert v.current_owner == buyer_member
        assert v.ownership_history.count() == 1
        assert transfer.previous_owner == sample_member


@pytest.mark.django_db
class TestDriverAndRouteAssignments:
    def test_driver_assignment_and_relief(self, sample_member, sacco_admin):
        v = Vehicle.objects.create(
            registration_number='KDD 555M',
            chassis_number='CHS-KDD555M',
            engine_number='ENG-KDD555M',
            make='Toyota',
            model='HiAce',
            year_of_manufacture=2021,
            category=VehicleCategory.MATATU_14,
            carrying_capacity=14,
            current_owner=sample_member
        )
        driver = Driver.objects.create(
            full_name='Ali Dima',
            national_id='11223344',
            phone_number='+254711223344',
            driving_license_number='DL-NTSA-5555',
            dl_expiry_date=date.today() + timedelta(days=300),
            emergency_contact_name='Fatuma Dima',
            emergency_contact_phone='+254711223345'
        )
        assignment = DriverAssignment.objects.create(
            driver=driver,
            vehicle=v,
            is_current=True,
            assigned_by=sacco_admin
        )
        assert assignment.is_current is True
        assert v.driver_assignments.filter(is_current=True).first().driver == driver

        # Relieve driver
        assignment.relieve()
        assert assignment.is_current is False
        assert assignment.relieved_at is not None

    def test_route_allocation(self, sample_member, sacco_admin):
        v = Vehicle.objects.create(
            registration_number='KDE 666N',
            chassis_number='CHS-KDE666N',
            engine_number='ENG-KDE666N',
            make='Scania',
            model='Bus',
            year_of_manufacture=2022,
            category=VehicleCategory.BUS_50_PLUS,
            carrying_capacity=52,
            current_owner=sample_member
        )
        route = Route.objects.create(
            route_code='NHT-TEST-01',
            name='Nairobi - Marsabit Direct',
            origin='Nairobi',
            destination='Marsabit',
            distance_km=Decimal('540.00'),
            intermediate_stops=['Nanyuki', 'Isiolo', 'Archer\'s Post']
        )
        route_alloc = VehicleRouteAssignment.objects.create(
            vehicle=v,
            route=route,
            road_service_license='RSL-TEST-2026',
            authorized_by=sacco_admin
        )
        assert route_alloc.vehicle == v
        assert route_alloc.route == route
        assert v.route_allocations.first().route.route_code == 'NHT-TEST-01'
