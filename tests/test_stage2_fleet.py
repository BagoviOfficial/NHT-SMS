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


@pytest.mark.django_db
class TestDriverRegistrationAllocationAndAdminEdit:
    def test_register_driver_with_license_details_vehicle_and_portal(self, client, sample_member, sacco_admin):
        v1 = Vehicle.objects.create(
            registration_number='KDG 101A',
            chassis_number='CHS-KDG101A',
            engine_number='ENG-KDG101A',
            make='Isuzu',
            model='FVZ',
            year_of_manufacture=2023,
            category=VehicleCategory.HEAVY_TRUCK,
            carrying_capacity=20,
            current_owner=sample_member,
            status=VehicleStatus.ACTIVE,
        )
        client.force_login(sacco_admin)
        today = date.today()
        res = client.post('/api/v1/drivers/', {
            'full_name': 'Hassan Abdullahi',
            'national_id': '22334455',
            'phone_number': '+254722334455',
            'email': 'hassan.driver@nhttransporters.co.ke',
            'driving_license_number': 'dl-ntsa-7788',
            'dl_class': 'ce',
            'dl_issue_date': str(today - timedelta(days=30)),
            'dl_expiry_date': str(today + timedelta(days=365)),
            'psv_badge_number': 'COM-2026-7788',
            'psv_badge_expiry': str(today + timedelta(days=300)),
            'emergency_contact_name': 'Halima Abdullahi',
            'emergency_contact_phone': '+254722334456',
            'status': DriverStatus.ACTIVE,
            'vehicle': str(v1.pk),
            'create_portal_account': True,
            'portal_username': 'hassan_drv',
        }, content_type='application/json')

        assert res.status_code == 201
        data = res.json()
        assert data['driving_license_number'] == 'DL-NTSA-7788'
        assert data['dl_class'] == 'CE'
        assert data['dl_issue_date'] == str(today - timedelta(days=30))
        assert data['dl_expiry_date'] == str(today + timedelta(days=365))
        assert data['psv_badge_number'] == 'COM-2026-7788'
        assert data['current_vehicle'] == str(v1.pk)
        assert data['current_vehicle_plate'] == 'KDG 101A'
        assert data['has_portal_account'] is True
        assert data['username'] == 'hassan_drv'

        creds = data['provisioned_portal_credentials']
        assert creds['username'] == 'hassan_drv'
        assert creds['generated'] is True

        driver = Driver.objects.get(pk=data['id'])
        assert driver.user.role == UserRole.DRIVER
        assert driver.user.is_staff is False
        assert DriverAssignment.objects.filter(driver=driver, vehicle=v1, is_current=True).exists()

        # Newly provisioned driver can log in, change temporary password, and view allocated vehicle & license in Driver Portal
        client.logout()
        login_res = client.post('/api/v1/auth/login/', {
            'username': 'hassan_drv',
            'password': creds['temporary_password'],
        }, content_type='application/json')
        assert login_res.status_code == 200
        assert login_res.json()['user']['must_change_password'] is True

        pw_change = client.post('/api/v1/auth/password-change/', {
            'old_password': creds['temporary_password'],
            'new_password': 'DriverNewStrong!2026',
        }, content_type='application/json')
        assert pw_change.status_code == 200

        portal_res = client.get('/api/v1/driver/portal/')
        assert portal_res.status_code == 200
        portal_data = portal_res.json()
        assert portal_data['driver']['dl_class'] == 'CE'
        assert portal_data['assigned_vehicles'][0]['registration_number'] == 'KDG 101A'

    def test_register_driver_rejects_expiry_before_issue_date(self, client, sacco_admin):
        client.force_login(sacco_admin)
        today = date.today()
        before = Driver.objects.count()
        res = client.post('/api/v1/drivers/', {
            'full_name': 'Invalid Dates Driver',
            'national_id': '22334499',
            'phone_number': '+254722334499',
            'driving_license_number': 'DL-BAD-01',
            'dl_issue_date': str(today),
            'dl_expiry_date': str(today - timedelta(days=5)),
            'emergency_contact_name': 'Kin',
            'emergency_contact_phone': '+254722334498',
        }, content_type='application/json')
        assert res.status_code == 400
        assert Driver.objects.count() == before

    def test_admin_can_edit_driver_details_and_vehicle_allocation(self, client, sample_member, sacco_admin):
        v1 = Vehicle.objects.create(
            registration_number='KDH 201B',
            chassis_number='CHS-KDH201B',
            engine_number='ENG-KDH201B',
            make='Mercedes-Benz',
            model='Actros',
            year_of_manufacture=2023,
            category=VehicleCategory.PRIME_MOVER,
            carrying_capacity=28,
            current_owner=sample_member,
            status=VehicleStatus.ACTIVE,
        )
        v2 = Vehicle.objects.create(
            registration_number='KDH 202B',
            chassis_number='CHS-KDH202B',
            engine_number='ENG-KDH202B',
            make='Scania',
            model='R450',
            year_of_manufacture=2024,
            category=VehicleCategory.PRIME_MOVER,
            carrying_capacity=30,
            current_owner=sample_member,
            status=VehicleStatus.ACTIVE,
        )
        client.force_login(sacco_admin)
        today = date.today()
        create_res = client.post('/api/v1/drivers/', {
            'full_name': 'Mohamed Noor',
            'national_id': '33445511',
            'phone_number': '+254733445511',
            'email': 'mohamed.noor@nhttransporters.co.ke',
            'driving_license_number': 'DL-NTSA-8801',
            'dl_class': 'C1',
            'dl_issue_date': str(today - timedelta(days=60)),
            'dl_expiry_date': str(today + timedelta(days=180)),
            'emergency_contact_name': 'Faduma Noor',
            'emergency_contact_phone': '+254733445512',
            'vehicle': str(v1.pk),
            'create_portal_account': True,
        }, content_type='application/json')
        assert create_res.status_code == 201
        drv_id = create_res.json()['id']

        # Admin edits driver personal, DL details, status, and reassigns vehicle to v2
        patch_res = client.patch(f'/api/v1/drivers/{drv_id}/', {
            'full_name': 'Mohamed Noor Aden',
            'phone_number': '+254733445599',
            'driving_license_number': 'dl-ntsa-8801-u',
            'dl_class': 'bce',
            'dl_expiry_date': str(today + timedelta(days=730)),
            'psv_badge_number': 'COM-2026-8801',
            'status': DriverStatus.ON_LEAVE,
            'vehicle': str(v2.pk),
        }, content_type='application/json')
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated['full_name'] == 'Mohamed Noor Aden'
        assert updated['phone_number'] == '+254733445599'
        assert updated['driving_license_number'] == 'DL-NTSA-8801-U'
        assert updated['dl_class'] == 'BCE'
        assert updated['dl_expiry_date'] == str(today + timedelta(days=730))
        assert updated['psv_badge_number'] == 'COM-2026-8801'
        assert updated['status'] == DriverStatus.ON_LEAVE
        assert updated['current_vehicle'] == str(v2.pk)
        assert updated['current_vehicle_plate'] == 'KDH 202B'

        driver = Driver.objects.get(pk=drv_id)
        assert driver.user.first_name == 'Mohamed'
        assert driver.user.last_name == 'Noor Aden'
        assert DriverAssignment.objects.filter(driver=driver, vehicle=v1, is_current=False).exists()
        assert DriverAssignment.objects.filter(driver=driver, vehicle=v2, is_current=True).exists()

        # Admin can also clear vehicle allocation via empty value
        clear_res = client.patch(f'/api/v1/drivers/{drv_id}/', {
            'vehicle': '',
        }, content_type='application/json')
        assert clear_res.status_code == 200
        assert clear_res.json()['current_vehicle'] is None
        assert clear_res.json()['current_vehicle_plate'] == ''
        assert not DriverAssignment.objects.filter(driver=driver, is_current=True).exists()

    def test_driver_registration_and_edit_rbac_and_portal_provisioning(self, client, sample_member, sacco_admin):
        v = Vehicle.objects.create(
            registration_number='KDJ 303C',
            chassis_number='CHS-KDJ303C',
            engine_number='ENG-KDJ303C',
            make='Volvo',
            model='FH16',
            year_of_manufacture=2024,
            category=VehicleCategory.HEAVY_TRUCK,
            carrying_capacity=25,
            current_owner=sample_member,
            status=VehicleStatus.ACTIVE,
        )
        today = date.today()
        driver_user = User.objects.create_user(
            username='drv_rbac_user',
            email='drv_rbac@nhttransporters.co.ke',
            password='DriverPassword123!',
            role=UserRole.DRIVER,
        )
        auditor = User.objects.create_user(
            username='aud_rbac_user',
            email='aud_rbac@nhttransporters.co.ke',
            password='AuditorPassword123!',
            role=UserRole.AUDITOR,
        )
        compliance = User.objects.create_user(
            username='comp_rbac_user',
            email='comp_rbac@nhttransporters.co.ke',
            password='CompliancePassword123!',
            role=UserRole.COMPLIANCE_OFFICER,
        )
        driver = Driver.objects.create(
            user=driver_user,
            full_name='John Kamau',
            national_id='44556611',
            phone_number='+254744556611',
            driving_license_number='DL-RBAC-01',
            dl_expiry_date=today + timedelta(days=100),
            emergency_contact_name='Mary Kamau',
            emergency_contact_phone='+254744556612',
        )

        # Drivers, Members, and Auditors cannot register or edit drivers
        for non_admin in (driver_user, sample_member.user, auditor):
            client.force_login(non_admin)
            assert client.post('/api/v1/drivers/', {
                'full_name': 'Unauthorized Driver',
                'national_id': '00001111',
                'phone_number': '+254700001111',
                'driving_license_number': 'DL-UNAUTH',
                'dl_expiry_date': str(today + timedelta(days=50)),
                'emergency_contact_name': 'Kin',
                'emergency_contact_phone': '+254700001112',
            }, content_type='application/json').status_code == 403
            assert client.patch(f'/api/v1/drivers/{driver.pk}/', {
                'full_name': 'Tampered Name',
            }, content_type='application/json').status_code == 403

        # Compliance Officer cannot allocate vehicles through driver edit, but can update DL details
        client.force_login(compliance)
        assert client.patch(f'/api/v1/drivers/{driver.pk}/', {
            'vehicle': str(v.pk),
        }, content_type='application/json').status_code == 403
        assert client.patch(f'/api/v1/drivers/{driver.pk}/', {
            'dl_class': 'CE',
        }, content_type='application/json').status_code == 200

        # Admin provisions portal account for an unlinked driver
        client.force_login(sacco_admin)
        unlinked = Driver.objects.create(
            full_name='Peter Wanjala',
            national_id='44556622',
            phone_number='+254744556622',
            driving_license_number='DL-UNLINKED-02',
            dl_expiry_date=today + timedelta(days=200),
            emergency_contact_name='Jane Wanjala',
            emergency_contact_phone='+254744556623',
        )
        prov_res = client.post(f'/api/v1/drivers/{unlinked.pk}/provision_portal_account/', {
            'email': 'peter.wanjala@nhttransporters.co.ke',
            'must_change_password': True,
        }, content_type='application/json')
        assert prov_res.status_code == 200
        assert prov_res.json()['has_portal_account'] is True
        unlinked.refresh_from_db()
        assert unlinked.user is not None
        assert unlinked.user.role == UserRole.DRIVER
