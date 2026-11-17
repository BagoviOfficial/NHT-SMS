import pytest
import uuid
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipStatus, MembershipCategory
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus, VehicleCategory, FuelType
from nht_sacco.apps.documents.models import Document, DocumentType, DocumentCategory
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus, ServiceItem, InvoiceItem
from nht_sacco.apps.payments.models import Payment, PaymentStatus, PaymentMethod, Receipt
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.notifications.models import (
    Notification,
    NotificationTemplate,
    NotificationChannel,
    NotificationStatus,
    NotificationCategory,
    CommunicationPreference,
    Announcement,
)
from nht_sacco.apps.notifications.adapters import (
    AfricasTalkingSMSAdapter,
    MetaWhatsAppAdapter,
    EmailNotificationAdapter,
    InAppNotificationAdapter,
)
from nht_sacco.apps.notifications.services import NotificationDispatcherService
from nht_sacco.apps.incidents.models import Incident, IncidentType, IncidentSeverity, IncidentStatus

User = get_user_model()


@pytest.fixture
def member_user_a(db):
    user = User.objects.create_user(
        username="member_a",
        email="member_a@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711000101",
        national_id="11111111",
        role=UserRole.MEMBER
    )
    member = Member.objects.create(
        user=user,
        membership_number="NHT-MBR-2026-0101",
        first_name="Abdi",
        last_name="Hassan",
        national_id="11111111",
        phone_number="+254711000101",
        email="member_a@northernhighways.co.ke",
        county="Isiolo",
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE
    )
    return user


@pytest.fixture
def member_user_b(db):
    user = User.objects.create_user(
        username="member_b",
        email="member_b@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711000102",
        national_id="22222222",
        role=UserRole.MEMBER
    )
    member = Member.objects.create(
        user=user,
        membership_number="NHT-MBR-2026-0102",
        first_name="Fatuma",
        last_name="Mohamed",
        national_id="22222222",
        phone_number="+254711000102",
        email="member_b@northernhighways.co.ke",
        county="Marsabit",
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE
    )
    return user


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="clerk_officer",
        email="clerk@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711000199",
        national_id="99999999",
        role=UserRole.RENEWAL_OFFICER
    )


@pytest.fixture
def vehicle_a(db, member_user_a):
    return Vehicle.objects.create(
        registration_number="KDA 555A",
        chassis_number="CHASSIS-A-555",
        engine_number="ENGINE-A-555",
        make="Toyota",
        model="HiAce",
        year_of_manufacture=2021,
        carrying_capacity=14,
        category=VehicleCategory.MATATU_14,
        fuel_type=FuelType.DIESEL,
        current_owner=member_user_a.member_profile,
        status=VehicleStatus.ACTIVE,
        created_by=member_user_a
    )


@pytest.fixture
def vehicle_b(db, member_user_b):
    return Vehicle.objects.create(
        registration_number="KDA 777B",
        chassis_number="CHASSIS-B-777",
        engine_number="ENGINE-B-777",
        make="Isuzu",
        model="NQR",
        year_of_manufacture=2022,
        carrying_capacity=33,
        category=VehicleCategory.MINIBUS_33,
        fuel_type=FuelType.DIESEL,
        current_owner=member_user_b.member_profile,
        status=VehicleStatus.ACTIVE,
        created_by=member_user_b
    )


@pytest.fixture
def doc_type_inspection(db):
    return DocumentType.objects.create(
        name="Annual NTSA Motor Vehicle Inspection",
        category=DocumentCategory.INSPECTION,
        standard_validity_months=12,
        is_mandatory_for_vehicle=True,
        reminder_thresholds=[30, 14, 7, 3, 0]
    )


@pytest.mark.django_db
class TestNotificationAdaptersAndDispatcher:
    def test_adapters_simulation_mode(self):
        # 1. Africa's Talking SMS Adapter
        sms_adapter = AfricasTalkingSMSAdapter()
        res_sms = sms_adapter.send(recipient="0711000101", title="Test", message="Hello SMS")
        assert res_sms['success'] is True
        assert res_sms['status'] == NotificationStatus.SENT
        assert res_sms['external_id'].startswith("AT_MSG_")

        # 2. Meta WhatsApp Adapter
        wa_adapter = MetaWhatsAppAdapter()
        res_wa = wa_adapter.send(recipient="+254711000101", title="Test", message="Hello WhatsApp")
        assert res_wa['success'] is True
        assert res_wa['status'] == NotificationStatus.SENT
        assert res_wa['external_id'].startswith("wamid.")

        # 3. Email Adapter
        email_adapter = EmailNotificationAdapter()
        res_email = email_adapter.send(recipient="member@northernhighways.co.ke", title="Test Subject", message="Hello Email")
        assert res_email['success'] is True
        assert res_email['status'] == NotificationStatus.SENT

        # 4. In-App Adapter
        inapp_adapter = InAppNotificationAdapter()
        res_inapp = inapp_adapter.send(recipient="member_a", title="Test Title", message="Hello InApp")
        assert res_inapp['success'] is True
        assert res_inapp['status'] == NotificationStatus.DELIVERED

    def test_dispatcher_respects_communication_preferences(self, member_user_a):
        member = member_user_a.member_profile
        pref = NotificationDispatcherService.get_or_create_preferences(member)
        pref.sms_enabled = True
        pref.whatsapp_enabled = False
        pref.in_app_enabled = True
        pref.save()

        notifs = NotificationDispatcherService.dispatch_to_member(
            member=member,
            category=NotificationCategory.BILLING,
            title="Invoice Generated",
            message="Your invoice is ready.",
            channels=[NotificationChannel.SMS, NotificationChannel.WHATSAPP, NotificationChannel.IN_APP]
        )

        channels_sent = [n.channel for n in notifs]
        assert NotificationChannel.SMS in channels_sent
        assert NotificationChannel.IN_APP in channels_sent
        assert NotificationChannel.WHATSAPP not in channels_sent

    def test_dispatcher_respects_category_opt_outs(self, member_user_a):
        member = member_user_a.member_profile
        pref = NotificationDispatcherService.get_or_create_preferences(member)
        pref.compliance_alerts = False
        pref.save()

        notifs = NotificationDispatcherService.dispatch_to_member(
            member=member,
            category=NotificationCategory.COMPLIANCE,
            title="Expiring Document",
            message="Your permit is expiring.",
        )
        assert len(notifs) == 0

    def test_template_rendering(self, member_user_a):
        member = member_user_a.member_profile
        tpl = NotificationTemplate.objects.create(
            code="TEST_COMPLIANCE_TPL",
            name="Test Template",
            channel=NotificationChannel.SMS,
            body_template="Permit {doc_type} for vehicle {vehicle_plate} expires on {date}."
        )

        notifs = NotificationDispatcherService.dispatch_to_member(
            member=member,
            category=NotificationCategory.COMPLIANCE,
            title="Permit Expiry",
            message="Default fallback",
            template_code="TEST_COMPLIANCE_TPL",
            context={'doc_type': 'Inspection', 'vehicle_plate': 'KDA 555A', 'date': '2026-12-31'},
            channels=[NotificationChannel.SMS]
        )

        assert len(notifs) == 1
        assert "Permit Inspection for vehicle KDA 555A expires on 2026-12-31." in notifs[0].message

    def test_broadcast_announcement(self, member_user_a, member_user_b):
        ann = Announcement.objects.create(
            title="Annual General Meeting",
            content="AGM will take place on Dec 15th at Isiolo Stadium.",
            published_by=member_user_a
        )
        count = NotificationDispatcherService.broadcast_announcement(ann)
        assert count >= 2
        assert Notification.objects.filter(title__contains="Annual General Meeting").count() >= 2


@pytest.mark.django_db
class TestMemberPortalAccessAndAntiIDOR:
    def test_unauthenticated_user_redirected(self, client):
        resp = client.get(reverse('portal:dashboard'))
        assert resp.status_code == 302
        assert '/accounts/login/' in resp.url

    def test_staff_account_without_member_profile_forbidden(self, client, staff_user):
        client.force_login(staff_user)
        resp = client.get(reverse('portal:dashboard'))
        # Should raise PermissionDenied -> 403 Forbidden
        assert resp.status_code == 403

    def test_member_accesses_own_portal_dashboard(self, client, member_user_a):
        client.force_login(member_user_a)
        resp = client.get(reverse('portal:dashboard'))
        assert resp.status_code == 200
        assert "Abdi" in resp.content.decode()
        assert "NHT-MBR-2026-0101" in resp.content.decode()

    def test_member_views_own_vehicles(self, client, member_user_a, vehicle_a):
        client.force_login(member_user_a)
        resp = client.get(reverse('portal:vehicles'))
        assert resp.status_code == 200
        assert "KDA 555A" in resp.content.decode()

    def test_anti_idor_member_blocked_from_other_members_vehicle(self, client, member_user_a, vehicle_b):
        """
        Anti-IDOR: Member A attempts to view Member B's vehicle details.
        Must return 403 Forbidden and record security violation in audit log.
        """
        client.force_login(member_user_a)
        resp = client.get(reverse('portal:vehicle_detail', kwargs={'vehicle_id': vehicle_b.id}))
        assert resp.status_code == 403

    def test_anti_idor_member_blocked_from_other_members_card(self, client, member_user_a, vehicle_b):
        client.force_login(member_user_a)
        resp = client.get(reverse('portal:vehicle_card', kwargs={'vehicle_id': vehicle_b.id}))
        assert resp.status_code == 403

    def test_anti_idor_member_blocked_from_other_members_invoice(self, client, member_user_a, member_user_b):
        inv_b = Invoice.objects.create(
            invoice_number="NHT-INV-2026-0999",
            member=member_user_b.member_profile,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            subtotal=Decimal('5000.00'),
            total_amount=Decimal('5000.00'),
            status=InvoiceStatus.ISSUED
        )
        client.force_login(member_user_a)
        resp = client.get(reverse('portal:invoice_detail', kwargs={'invoice_id': inv_b.id}))
        assert resp.status_code == 403

        # Attempting STK Push on Member B's invoice
        resp_stk = client.post(reverse('portal:invoice_pay_stk', kwargs={'invoice_id': inv_b.id}))
        assert resp_stk.status_code == 403


@pytest.mark.django_db
class TestMemberPortalFeatures:
    def test_vehicle_registration_request(self, client, member_user_a):
        client.force_login(member_user_a)
        resp = client.post(reverse('portal:vehicle_register'), {
            'registration_number': 'KDA 999Z',
            'make': 'Toyota',
            'model': 'HiAce',
            'year_of_manufacture': 2023,
            'category': VehicleCategory.MATATU_14,
            'fuel_type': FuelType.DIESEL,
            'carrying_capacity': 14,
            'chassis_number': 'VIN-TEST-999Z',
            'engine_number': 'ENG-TEST-999Z',
        }, follow=True)

        assert resp.status_code == 200
        v = Vehicle.objects.filter(registration_number="KDA 999Z").first()
        assert v is not None
        assert v.current_owner == member_user_a.member_profile
        assert v.status == VehicleStatus.PENDING

    def test_renewal_application_submission(self, client, member_user_a, vehicle_a, doc_type_inspection):
        client.force_login(member_user_a)
        resp = client.post(reverse('portal:renewal_apply'), {
            'vehicle_id': str(vehicle_a.id),
            'document_type_id': str(doc_type_inspection.id),
            'notes': 'Please expedite renewal for upcoming route inspection.',
        }, follow=True)

        assert resp.status_code == 200
        rnw = RenewalRequest.objects.filter(vehicle=vehicle_a, document_type=doc_type_inspection).first()
        assert rnw is not None
        assert rnw.member == member_user_a.member_profile
        assert rnw.status == RenewalStatus.SUBMITTED

    def test_member_financial_statement_ledger_calculation(self, client, member_user_a):
        member = member_user_a.member_profile

        # Invoice 1: 10,000
        inv1 = Invoice.objects.create(
            invoice_number="NHT-INV-2026-0001",
            member=member,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            subtotal=Decimal('10000.00'),
            total_amount=Decimal('10000.00'),
            amount_paid=Decimal('4000.00'),
            status=InvoiceStatus.PARTIALLY_PAID
        )

        # Payment 1: 4,000 towards Invoice 1
        p1 = Payment.objects.create(
            invoice=inv1,
            member=member,
            payment_reference="NHT-PAY-2026-0001",
            provider_transaction_id="MPESA-REC-001",
            method=PaymentMethod.MPESA,
            amount=Decimal('4000.00'),
            idempotency_key="IDEMP-STK-001",
            status=PaymentStatus.SUCCESS,
            confirmed_at=timezone.now()
        )

        client.force_login(member_user_a)
        resp = client.get(reverse('portal:statement'))
        assert resp.status_code == 200
        content = resp.content.decode()

        assert "NHT-INV-2026-0001" in content
        assert "MPESA-REC-001" in content
        # Running balance should be 6000.00
        assert "6,000.00" in content or "6000.00" in content

    def test_complaint_ticket_submission(self, client, member_user_a, vehicle_a):
        client.force_login(member_user_a)
        resp = client.post(reverse('portal:complaint_submit'), {
            'incident_type': IncidentType.COMPLAINT,
            'severity': IncidentSeverity.HIGH,
            'vehicle_id': str(vehicle_a.id),
            'location': 'Isiolo Stage',
            'title': 'Queue disruption at departure stage',
            'description': 'Dispute regarding departure scheduling order.',
        }, follow=True)

        assert resp.status_code == 200
        inc = Incident.objects.filter(reported_by_member=member_user_a.member_profile).first()
        assert inc is not None
        assert inc.ticket_number.startswith("NHT-INC-")
        assert inc.severity == IncidentSeverity.HIGH
        assert inc.status == IncidentStatus.SUBMITTED

    def test_notification_mark_read(self, client, member_user_a):
        notif = Notification.objects.create(
            recipient_user=member_user_a,
            recipient_member=member_user_a.member_profile,
            channel=NotificationChannel.IN_APP,
            category=NotificationCategory.ANNOUNCEMENT,
            title="System Maintenance",
            message="Maintenance tonight at 23:00.",
            status=NotificationStatus.DELIVERED
        )
        client.force_login(member_user_a)
        resp = client.post(reverse('portal:notification_read', kwargs={'notif_id': notif.id}), follow=True)
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.status == NotificationStatus.READ
        assert notif.read_at is not None
