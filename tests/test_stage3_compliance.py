import pytest
from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from nht_sacco.apps.documents.models import DocumentType, Document, DocumentCategory, VerificationStatus
from nht_sacco.apps.compliance.models import ComplianceStatus, ComplianceAlert
from nht_sacco.apps.compliance.services import ComplianceService

User = get_user_model()

@pytest.fixture
def compliance_officer(db):
    return User.objects.create_user(
        username='compliance_user',
        email='compliance@nhttransporters.co.ke',
        password='OfficerPassword123!',
        role=UserRole.COMPLIANCE_OFFICER
    )

@pytest.fixture
def member_one(db):
    u = User.objects.create_user(
        username='m_one',
        email='m1@nhttransporters.co.ke',
        password='Password123!',
        role=UserRole.MEMBER
    )
    return Member.objects.create(
        user=u,
        membership_number='NHT-MBR-2026-0101',
        first_name='Abdi',
        last_name='Kassim',
        national_id='22334411',
        phone_number='+254711000101',
        email='m1@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin',
        next_of_kin_relation='Spouse',
        next_of_kin_phone='+254711000102'
    )

@pytest.fixture
def member_two(db):
    u = User.objects.create_user(
        username='m_two',
        email='m2@nhttransporters.co.ke',
        password='Password123!',
        role=UserRole.MEMBER
    )
    return Member.objects.create(
        user=u,
        membership_number='NHT-MBR-2026-0202',
        first_name='Jibril',
        last_name='Noor',
        national_id='22334422',
        phone_number='+254711000202',
        email='m2@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin',
        next_of_kin_relation='Brother',
        next_of_kin_phone='+254711000203'
    )

@pytest.fixture
def vehicle_one(db, member_one):
    return Vehicle.objects.create(
        registration_number='KDA 505M',
        chassis_number='CHS-505M',
        engine_number='ENG-505M',
        make='Toyota',
        model='HiAce',
        year_of_manufacture=2021,
        category=VehicleCategory.MATATU_14,
        carrying_capacity=14,
        current_owner=member_one,
        status=VehicleStatus.ACTIVE
    )

@pytest.fixture
def sample_doc_type(db):
    return DocumentType.objects.create(
        name='Test Inspection Certificate',
        category=DocumentCategory.INSPECTION,
        standard_validity_months=6,
        reminder_thresholds=[30, 14, 7, 3, 0],
        is_mandatory_for_vehicle=True
    )

@pytest.mark.django_db
class TestDocumentVaultAndPermissions:
    def test_document_hash_computation(self, vehicle_one, sample_doc_type, compliance_officer):
        sample_file = SimpleUploadedFile("cert.pdf", b"%PDF-1.4 test certificate content", content_type="application/pdf")
        doc = Document.objects.create(
            document_type=sample_doc_type,
            vehicle=vehicle_one,
            reference_number='CERT-TEST-001',
            issue_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=150),
            file=sample_file,
            uploaded_by=compliance_officer,
            status=VerificationStatus.VERIFIED
        )
        assert doc.file_hash != ''
        assert len(doc.file_hash) == 64

    def test_document_access_control_idor_prevention(self, client, vehicle_one, sample_doc_type, member_one, member_two, compliance_officer):
        sample_file = SimpleUploadedFile("cert.pdf", b"Confidential Certificate Content", content_type="application/pdf")
        doc = Document.objects.create(
            document_type=sample_doc_type,
            vehicle=vehicle_one,
            reference_number='CERT-SECRET-001',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=90),
            file=sample_file,
            uploaded_by=compliance_officer,
            status=VerificationStatus.VERIFIED
        )

        url = reverse('documents:document_download', kwargs={'pk': doc.pk})

        # 1. Anonymous user redirected to login
        res_anon = client.get(url)
        assert res_anon.status_code == 302
        assert '/accounts/login/' in res_anon.url

        # 2. Member 2 (not the owner) gets 403 Forbidden
        client.force_login(member_two.user)
        res_m2 = client.get(url)
        assert res_m2.status_code == 403

        # 3. Member 1 (the legitimate vehicle owner) gets 200 OK
        client.force_login(member_one.user)
        res_m1 = client.get(url)
        assert res_m1.status_code == 200

        # 4. Compliance Officer gets 200 OK
        client.force_login(compliance_officer)
        res_officer = client.get(url)
        assert res_officer.status_code == 200


@pytest.mark.django_db
class TestComplianceEngine:
    def test_compliance_status_calculation(self, vehicle_one, compliance_officer):
        # Create 2 mandatory document types
        dt1 = DocumentType.objects.create(name='Mandatory PSV Inspection', category=DocumentCategory.INSPECTION, is_mandatory_for_vehicle=True)
        dt2 = DocumentType.objects.create(name='Mandatory PSV Insurance', category=DocumentCategory.INSURANCE, is_mandatory_for_vehicle=True)

        # Initially, with no documents uploaded, vehicle is NON_COMPLIANT
        status_info = ComplianceService.get_vehicle_compliance_status(vehicle_one)
        assert status_info['status'] == ComplianceStatus.NON_COMPLIANT
        assert dt1 in status_info['missing_mandatory']
        assert dt2 in status_info['missing_mandatory']

        # Upload both documents with 60 days validity -> FULLY_COMPLIANT
        doc1 = Document.objects.create(
            document_type=dt1,
            vehicle=vehicle_one,
            reference_number='INSP-001',
            issue_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=60),
            file=SimpleUploadedFile("insp.pdf", b"test content"),
            status=VerificationStatus.VERIFIED
        )
        doc2 = Document.objects.create(
            document_type=dt2,
            vehicle=vehicle_one,
            reference_number='INS-001',
            issue_date=date.today() - timedelta(days=30),
            expiry_date=date.today() + timedelta(days=60),
            file=SimpleUploadedFile("ins.pdf", b"test content"),
            status=VerificationStatus.VERIFIED
        )
        status_info = ComplianceService.get_vehicle_compliance_status(vehicle_one)
        assert status_info['status'] == ComplianceStatus.FULLY_COMPLIANT

        # Update doc1 to expire in 7 days -> EXPIRING_SOON
        doc1.expiry_date = date.today() + timedelta(days=7)
        doc1.save()
        status_info = ComplianceService.get_vehicle_compliance_status(vehicle_one)
        assert status_info['status'] == ComplianceStatus.EXPIRING_SOON

        # Update doc1 to expired yesterday -> NON_COMPLIANT
        doc1.expiry_date = date.today() - timedelta(days=1)
        doc1.save()
        status_info = ComplianceService.get_vehicle_compliance_status(vehicle_one)
        assert status_info['status'] == ComplianceStatus.NON_COMPLIANT

    def test_daily_compliance_scan_generates_alerts(self, vehicle_one, compliance_officer):
        dt = DocumentType.objects.create(
            name='Daily Scan Inspection',
            category=DocumentCategory.INSPECTION,
            is_mandatory_for_vehicle=True,
            reminder_thresholds=[30, 14, 7, 3, 0]
        )
        # Create document expiring in exactly 7 days
        Document.objects.create(
            document_type=dt,
            vehicle=vehicle_one,
            reference_number='SCAN-7DAY-001',
            issue_date=date.today() - timedelta(days=100),
            expiry_date=date.today() + timedelta(days=7),
            file=SimpleUploadedFile("scan.pdf", b"test"),
            status=VerificationStatus.VERIFIED
        )

        scan_result = ComplianceService.run_daily_compliance_scan()
        assert scan_result['total_vehicles_scanned'] >= 1
        assert scan_result['alerts_created'] >= 1
        alert = ComplianceAlert.objects.filter(vehicle=vehicle_one, alert_type=ComplianceAlert.AlertType.UPCOMING_EXPIRY).first()
        assert alert is not None
        assert alert.days_remaining == 7


@pytest.mark.django_db
class TestPublicQRVerificationView:
    def test_public_qr_verification_endpoint(self, client, vehicle_one):
        url = reverse('vehicle_public_verify', kwargs={'qr_token': vehicle_one.qr_token})
        response = client.get(url)
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Check registration plate is present
        assert vehicle_one.registration_number in content
        # Check SACCO verification seal is present
        assert 'Northern Highways Transporters' in content

        # CRITICAL SECURITY CHECK: Zero PII
        # Ensure national ID is NOT present anywhere on public page
        assert vehicle_one.current_owner.national_id not in content
        # Ensure phone number is NOT present
        assert vehicle_one.current_owner.phone_number not in content
        # Ensure private document links are NOT present
        assert '/documents/' not in content
