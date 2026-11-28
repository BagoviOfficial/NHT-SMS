import io
import pytest
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
import openpyxl

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, FuelType, VehicleStatus
from nht_sacco.apps.routes.models import Route
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus, PaymentMethod
from nht_sacco.apps.accounting.models import Expense
from nht_sacco.apps.maintenance.models import (
    MaintenanceProvider,
    MaintenanceRecord,
    MaintenanceType,
    MaintenanceStatus,
    SparePart,
    MaintenancePartUsage
)
from nht_sacco.apps.maintenance.services import MaintenanceService
from nht_sacco.apps.governance.models import (
    Committee,
    CommitteeType,
    CommitteeMember,
    Meeting,
    MeetingStatus,
    MeetingAgenda,
    Resolution,
    ResolutionStatus,
    ActionItem
)
from nht_sacco.apps.governance.services import GovernanceService
from nht_sacco.apps.incidents.models import (
    Incident,
    IncidentType,
    IncidentSeverity,
    IncidentStatus,
    IncidentUpdate
)
from nht_sacco.apps.reports.services import ExecutiveDashboardMetrics, ReportExportService

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="sacco_admin",
        email="admin@northernhighways.co.ke",
        password="ValidPassword123!",
        role=UserRole.SUPER_ADMIN,
        is_staff=True
    )


@pytest.fixture
def finance_officer(db):
    return User.objects.create_user(
        username="treasurer_officer",
        email="treasurer@northernhighways.co.ke",
        password="ValidPassword123!",
        role=UserRole.TREASURER,
        is_staff=True
    )


@pytest.fixture
def member_user(db):
    user = User.objects.create_user(
        username="stage7_member",
        email="member_s7@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711999888",
        national_id="88887777",
        role=UserRole.MEMBER
    )
    member = Member.objects.create(
        user=user,
        membership_number="NHT-MBR-2026-0777",
        first_name="Hassan",
        last_name="Ali",
        national_id="88887777",
        phone_number="+254711999888",
        email="member_s7@northernhighways.co.ke",
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE
    )
    return user


@pytest.fixture
def vehicle_s7(db, member_user):
    return Vehicle.objects.create(
        registration_number="KDA 888S",
        chassis_number="CHASSIS-S7-888",
        engine_number="ENGINE-S7-888",
        make="Toyota",
        model="HiAce",
        year_of_manufacture=2022,
        carrying_capacity=14,
        category=VehicleCategory.MATATU_14,
        fuel_type=FuelType.DIESEL,
        current_owner=member_user.member_profile,
        status=VehicleStatus.ACTIVE,
        created_by=member_user
    )


@pytest.mark.django_db
class TestMaintenanceWorkflows:
    def test_maintenance_provider_and_spare_parts(self):
        provider = MaintenanceProvider.objects.create(
            name="Isiolo Heavy Diesel Works",
            contact_person="Mzee Juma",
            phone_number="+254722000111",
            physical_address="Isiolo Industrial Area",
            is_approved=True
        )
        assert str(provider).startswith("Isiolo Heavy Diesel Works")

        part = SparePart.objects.create(
            name="Front Brake Pads",
            part_number="BP-HIACE-01",
            category="Brakes",
            unit_cost=Decimal("4500.00"),
            quantity_in_stock=20
        )
        assert part.unit_cost == Decimal("4500.00")
        assert "BP-HIACE-01" in str(part)

    def test_work_order_creation_and_auto_numbering(self, vehicle_s7, admin_user):
        provider = MaintenanceProvider.objects.create(
            name="Marsabit Auto Garage",
            contact_person="Abdirahman",
            phone_number="+254722000222",
            physical_address="Marsabit Central"
        )
        rec = MaintenanceRecord.objects.create(
            vehicle=vehicle_s7,
            provider=provider,
            maintenance_type=MaintenanceType.SCHEDULED_SERVICE,
            scheduled_date=timezone.now().date(),
            odometer_reading=45000,
            parts_cost=Decimal("6000.00"),
            labour_cost=Decimal("3000.00"),
            description="50,000KM Routine Service: Oil change and filter replacement",
            recorded_by=admin_user
        )

        assert rec.work_order_number.startswith("NHT-MNT-")
        assert rec.total_cost == Decimal("9000.00")
        assert rec.status == MaintenanceStatus.BOOKED

    def test_service_completion_and_metrics_summary(self, vehicle_s7, admin_user):
        provider = MaintenanceProvider.objects.create(
            name="Nanyuki Speed Garage",
            contact_person="Peter Kimani",
            phone_number="+254722000333",
            physical_address="Nanyuki Highway"
        )
        rec = MaintenanceRecord.objects.create(
            vehicle=vehicle_s7,
            provider=provider,
            maintenance_type=MaintenanceType.UNSCHEDULED_REPAIR,
            scheduled_date=timezone.now().date(),
            odometer_reading=52000,
            parts_cost=Decimal("12000.00"),
            labour_cost=Decimal("5000.00"),
            description="Alternator replacement due to charging failure",
            recorded_by=admin_user
        )

        MaintenanceService.complete_service(
            record=rec,
            verified_by=admin_user,
            downtime_hours=Decimal("8.50"),
            notes="Alternator bench tested and verified working under load."
        )

        rec.refresh_from_db()
        assert rec.status == MaintenanceStatus.COMPLETED
        assert rec.downtime_hours == Decimal("8.50")
        assert rec.verified_by == admin_user
        assert "bench tested" in rec.technician_notes

        # Vehicle summary
        v_summary = MaintenanceService.get_vehicle_maintenance_summary(vehicle_s7)
        assert v_summary['total_cost'] == Decimal("17000.00")
        assert v_summary['total_downtime_hours'] == Decimal("8.50")
        assert v_summary['total_services'] == 1

        # Fleet metrics
        fleet_metrics = MaintenanceService.get_fleet_maintenance_metrics()
        assert fleet_metrics['fleet_total_cost'] >= Decimal("17000.00")
        assert fleet_metrics['completed_count'] >= 1


@pytest.mark.django_db
class TestGovernanceWorkflows:
    def test_committee_and_meeting_lifecycle(self, admin_user, finance_officer):
        # 1. Committee
        board = Committee.objects.create(
            name="Board of Directors",
            committee_type=CommitteeType.EXECUTIVE,
            description="Supreme governing council of the SACCO",
            chairperson=admin_user,
            secretary=finance_officer
        )
        CommitteeMember.objects.create(
            committee=board,
            user=admin_user,
            role_title="Board Chairman"
        )
        assert board.memberships.count() == 1

        # 2. Meeting
        meeting = Meeting.objects.create(
            committee=board,
            title="Q4 Strategic Operations Review",
            scheduled_date=timezone.now(),
            location="SACCO Headquarters, Isiolo",
            status=MeetingStatus.SCHEDULED,
            convened_by=admin_user
        )
        assert meeting.meeting_number.startswith("NHT-MTG-")

        # 3. Agenda
        agenda1 = MeetingAgenda.objects.create(
            meeting=meeting,
            item_number=1,
            topic="Review of Fleet Route Compliance & KeNHA Permits",
            presenter="Compliance Officer",
            allocated_minutes=30
        )
        assert agenda1.item_number == 1

        # 4. Resolution & Voting
        res = Resolution.objects.create(
            meeting=meeting,
            title="Mandatory Bi-Weekly Fleet Maintenance Verification",
            description="Resolved that all 14-seater matatus must undergo bi-weekly safety checks.",
            proposer=admin_user,
            seconder=finance_officer
        )
        assert res.resolution_number.startswith("NHT-RES-")

        GovernanceService.record_vote(
            resolution=res,
            votes_for=7,
            votes_against=1,
            votes_abstained=1
        )
        res.refresh_from_db()
        assert res.status == ResolutionStatus.PASSED
        assert res.votes_for == 7

        # 5. Action Item Tracking
        action = ActionItem.objects.create(
            resolution=res,
            description="Circulate mandatory inspection guidelines to all vehicle owners",
            assigned_to=finance_officer,
            due_date=timezone.now().date() + timezone.timedelta(days=7)
        )
        assert action.is_completed is False

        GovernanceService.complete_action(
            action_item=action,
            notes="Circular dispatched to all active members via SMS and portal announcement."
        )
        action.refresh_from_db()
        assert action.is_completed is True
        assert action.completed_at is not None

        # Summary check
        gov_summary = GovernanceService.get_governance_summary()
        assert gov_summary['active_committees'] >= 1
        assert gov_summary['total_meetings'] >= 1
        assert gov_summary['passed_resolutions'] >= 1


@pytest.mark.django_db
class TestIncidentResolutionWorkflows:
    def test_incident_escalation_and_investigation_notes(self, member_user, vehicle_s7, admin_user):
        incident = Incident.objects.create(
            incident_type=IncidentType.ROUTE_DISPUTE,
            severity=IncidentSeverity.HIGH,
            reported_by_member=member_user.member_profile,
            vehicle=vehicle_s7,
            title="Unauthorized picking along Isiolo-Moyale corridor",
            description="Operator from rival route picked passengers at non-designated stage."
        )
        assert incident.ticket_number.startswith("NHT-INC-")
        assert incident.status == IncidentStatus.SUBMITTED

        # Officer assignment
        incident.assigned_officer = admin_user
        incident.status = IncidentStatus.UNDER_INVESTIGATION
        incident.save()

        # Update note
        update = IncidentUpdate.objects.create(
            incident=incident,
            author=admin_user,
            notes="Contacted stage marshal at Archer's Post for CCTV verification.",
            status_change="UNDER_INVESTIGATION"
        )
        assert incident.updates.count() == 1

        # Resolution
        incident.status = IncidentStatus.RESOLVED
        incident.resolution_notes = "Driver cautioned; fine issued according to SACCO bylaws."
        incident.resolved_at = timezone.now()
        incident.save()

        incident.refresh_from_db()
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None


@pytest.mark.django_db
class TestExecutiveReportingAndExports:
    def test_dashboard_metrics_aggregation(self, member_user, vehicle_s7):
        kpis = ExecutiveDashboardMetrics.get_kpis()
        assert 'total_members' in kpis
        assert 'compliance_rate' in kpis
        assert 'total_invoiced' in kpis
        assert 'total_collected' in kpis
        assert 'route_distribution' in kpis
        assert kpis['total_members'] >= 1
        assert kpis['total_vehicles'] >= 1

    def test_unauthorized_member_denied_access_to_dashboard(self, client, member_user):
        client.force_login(member_user)
        resp = client.get(reverse('reports:dashboard'))
        assert resp.status_code == 403

    def test_staff_access_reports_dashboard(self, client, admin_user):
        client.force_login(admin_user)
        resp = client.get(reverse('reports:dashboard'))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "Executive Reports &amp; Exports" in content or "Executive Reports & Exports" in content
        assert "@mui/material" in content
        assert '"reports"' in content

        summary_res = client.get('/api/v1/reports/summary/')
        assert summary_res.status_code == 200
        summary = summary_res.json()
        assert 'compliance_rate' in summary
        assert 'maintenance_summary' in summary

    def test_pdf_compliance_report_export(self, client, admin_user, vehicle_s7):
        client.force_login(admin_user)
        resp = client.get(reverse('reports:export_compliance_pdf'))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert "NHT_Fleet_Compliance_Report.pdf" in resp['Content-Disposition']
        # Verify valid PDF header
        assert resp.content.startswith(b"%PDF")

    def test_excel_financial_report_export(self, client, finance_officer):
        client.force_login(finance_officer)
        resp = client.get(reverse('reports:export_financial_excel'))
        assert resp.status_code == 200
        assert "spreadsheetml.sheet" in resp['Content-Type']
        assert "NHT_Financial_Summary.xlsx" in resp['Content-Disposition']

        # Parse with openpyxl to ensure validity
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        assert "Invoices" in wb.sheetnames
        assert "Receipts & Payments" in wb.sheetnames
