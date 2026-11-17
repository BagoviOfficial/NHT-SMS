import io
import pytest
from decimal import Decimal
from django.utils import timezone
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, FuelType, VehicleStatus
from nht_sacco.apps.documents.models import Document, DocumentType, DocumentCategory, VerificationStatus
from nht_sacco.apps.documents.validators import (
    validate_regulatory_document,
    validate_file_magic_bytes,
    MAX_FILE_SIZE_BYTES
)
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.accounting.models import JournalEntry, JournalLine, Account, AccountType, FinancialPeriod
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

User = get_user_model()


@pytest.fixture
def member_victim(db):
    user = User.objects.create_user(
        username="victim_member",
        email="victim@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711111222",
        national_id="33445566",
        role=UserRole.MEMBER
    )
    Member.objects.create(
        user=user,
        membership_number="NHT-MBR-2026-0334",
        first_name="Amina",
        last_name="Said",
        national_id="33445566",
        phone_number="+254711111222",
        email="victim@northernhighways.co.ke",
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE
    )
    return user


@pytest.fixture
def member_attacker(db):
    user = User.objects.create_user(
        username="attacker_member",
        email="attacker@northernhighways.co.ke",
        password="ValidPassword123!",
        phone_number="+254711333444",
        national_id="77889900",
        role=UserRole.MEMBER
    )
    Member.objects.create(
        user=user,
        membership_number="NHT-MBR-2026-0778",
        first_name="Malicious",
        last_name="Actor",
        national_id="77889900",
        phone_number="+254711333444",
        email="attacker@northernhighways.co.ke",
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE
    )
    return user


@pytest.fixture
def victim_vehicle(db, member_victim):
    return Vehicle.objects.create(
        registration_number="KDA 001V",
        chassis_number="CHASSIS-VICTIM-001",
        engine_number="ENG-VICTIM-001",
        make="Toyota",
        model="HiAce",
        year_of_manufacture=2021,
        carrying_capacity=14,
        category=VehicleCategory.MATATU_14,
        fuel_type=FuelType.DIESEL,
        current_owner=member_victim.member_profile,
        status=VehicleStatus.ACTIVE,
        created_by=member_victim
    )


@pytest.mark.django_db
class TestFileSecurityAndMagicByteValidation:
    def test_valid_pdf_magic_bytes_accepted(self):
        valid_pdf = SimpleUploadedFile("inspection.pdf", b"%PDF-1.5 \x00\x01\x02 test stream", content_type="application/pdf")
        validate_regulatory_document(valid_pdf)  # Should not raise

    def test_valid_jpeg_magic_bytes_accepted(self):
        valid_jpeg = SimpleUploadedFile("vehicle.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", content_type="image/jpeg")
        validate_regulatory_document(valid_jpeg)  # Should not raise

    def test_valid_png_magic_bytes_accepted(self):
        valid_png = SimpleUploadedFile("stamp.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", content_type="image/png")
        validate_regulatory_document(valid_png)  # Should not raise

    def test_disguised_executable_rejected_despite_pdf_extension(self):
        """
        OWASP ASVS: Attackers rename executable scripts (PHP/Bash) with a .pdf extension.
        Validator must detect signature mismatch and raise ValidationError.
        """
        malicious_file = SimpleUploadedFile("invoice.pdf", b"<?php system($_GET['cmd']); ?>", content_type="application/pdf")
        with pytest.raises(ValidationError) as exc:
            validate_regulatory_document(malicious_file)
        assert "signature does not match" in str(exc.value)

    def test_disallowed_extension_rejected(self):
        script_file = SimpleUploadedFile("exploit.sh", b"#!/bin/bash\nrm -rf /", content_type="application/x-sh")
        with pytest.raises(ValidationError) as exc:
            validate_regulatory_document(script_file)
        assert "prohibited" in str(exc.value)

    def test_oversized_file_rejected(self):
        oversized = SimpleUploadedFile("huge.pdf", b"%PDF-1.4 " + (b"A" * (MAX_FILE_SIZE_BYTES + 1024)), content_type="application/pdf")
        with pytest.raises(ValidationError) as exc:
            validate_regulatory_document(oversized)
        assert "exceeds the maximum permitted limit" in str(exc.value)


@pytest.mark.django_db
class TestAntiIDORProtection:
    def test_attacker_cannot_access_victim_vehicle_detail(self, client, member_attacker, victim_vehicle):
        client.force_login(member_attacker)
        resp = client.get(reverse('portal:vehicle_detail', kwargs={'vehicle_id': victim_vehicle.id}))
        assert resp.status_code == 403
        # Verify security denial was logged in immutable audit log
        assert AuditLog.objects.filter(
            actor=member_attacker,
            outcome=AuditOutcome.DENIED,
            entity_type='Vehicle'
        ).exists()

    def test_attacker_cannot_access_victim_vehicle_card(self, client, member_attacker, victim_vehicle):
        client.force_login(member_attacker)
        resp = client.get(reverse('portal:vehicle_card', kwargs={'vehicle_id': victim_vehicle.id}))
        assert resp.status_code == 403
        assert AuditLog.objects.filter(
            actor=member_attacker,
            outcome=AuditOutcome.DENIED,
            entity_type='VehicleCard'
        ).exists()

    def test_attacker_cannot_view_victim_invoice(self, client, member_attacker, member_victim):
        inv = Invoice.objects.create(
            invoice_number="NHT-INV-2026-0888",
            member=member_victim.member_profile,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            subtotal=Decimal("15000.00"),
            total_amount=Decimal("15000.00"),
            status=InvoiceStatus.ISSUED
        )
        client.force_login(member_attacker)
        resp = client.get(reverse('portal:invoice_detail', kwargs={'invoice_id': inv.id}))
        assert resp.status_code == 403
        assert AuditLog.objects.filter(
            actor=member_attacker,
            outcome=AuditOutcome.DENIED,
            entity_type='Invoice'
        ).exists()

    def test_attacker_cannot_initiate_payment_on_victim_invoice(self, client, member_attacker, member_victim):
        inv = Invoice.objects.create(
            invoice_number="NHT-INV-2026-0889",
            member=member_victim.member_profile,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            subtotal=Decimal("8000.00"),
            total_amount=Decimal("8000.00"),
            status=InvoiceStatus.ISSUED
        )
        client.force_login(member_attacker)
        resp = client.post(reverse('portal:invoice_pay_stk', kwargs={'invoice_id': inv.id}))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestAuditAndFinancialImmutability:
    def test_audit_log_entries_immutable(self, member_victim):
        log = AuditLog.objects.create(
            actor=member_victim,
            action=AuditAction.VIEW,
            entity_type='TestEntity',
            entity_id='12345',
            outcome=AuditOutcome.SUCCESS
        )

        # Modifying must fail
        with pytest.raises(ValidationError) as exc:
            log.action = AuditAction.DELETE
            log.save()
        assert "immutable" in str(exc.value)

        # Deleting must fail
        with pytest.raises(ValidationError) as exc_del:
            log.delete()
        assert "permanent" in str(exc_del.value)

    def test_posted_journal_entry_cannot_be_tampered(self, member_victim):
        period = FinancialPeriod.objects.create(
            name="Q4 2026",
            start_date=timezone.now().date() - timezone.timedelta(days=15),
            end_date=timezone.now().date() + timezone.timedelta(days=75)
        )
        acc_bank = Account.objects.create(code="1010", name="Bank", type=AccountType.ASSET)
        acc_rev = Account.objects.create(code="4010", name="Revenue", type=AccountType.REVENUE)

        entry = JournalEntry.objects.create(
            entry_number='NHT-JRN-2026-SEC01',
            date=timezone.now().date(),
            period=period,
            reference='SEC-REF-01',
            narration="Fee collection",
            posted_by=member_victim,
            is_posted=True
        )
        JournalLine.objects.create(journal_entry=entry, account=acc_bank, debit=Decimal("1000.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(journal_entry=entry, account=acc_rev, debit=Decimal("0.00"), credit=Decimal("1000.00"))
        entry.verify_balance()

        # Once posted, direct deletion must fail
        with pytest.raises(ValidationError) as exc_del:
            entry.delete()
        assert "cannot be deleted" in str(exc_del.value)

        # Modifying date or financial period must fail validation
        entry.date = timezone.now().date() - timezone.timedelta(days=10)
        with pytest.raises(ValidationError) as exc:
            entry.clean()
        assert "immutable" in str(exc.value)


@pytest.mark.django_db
class TestZeroPIIPublicVerification:
    def test_public_qr_verification_exposes_no_sensitive_pii(self, client, victim_vehicle):
        """
        OWASP Data Minimization: The public QR scan endpoint accessed by traffic police
        or passengers must NEVER expose personal identification, telephone numbers,
        financial records, or uploaded private vault documents.
        """
        resp = client.get(reverse('vehicle_public_verify', kwargs={'qr_token': victim_vehicle.qr_token}))
        assert resp.status_code == 200
        content = resp.content.decode()

        # Public details must exist
        assert victim_vehicle.registration_number in content

        # Sensitive PII must NOT exist anywhere in the public response
        assert "33445566" not in content  # Victim national ID
        assert "+254711111222" not in content  # Victim phone number
        assert "Amina Said" not in content  # Private owner identity
        assert "victim@northernhighways.co.ke" not in content  # Email
