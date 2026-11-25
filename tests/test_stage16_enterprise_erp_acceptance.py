import io
import os
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import openpyxl
from PIL import Image
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.billing.models import Invoice, InvoiceItem, ServiceItem
from nht_sacco.apps.documents.models import Document, DocumentCategory, DocumentType, VerificationStatus
from nht_sacco.apps.integrations.branding import DocumentBrandingService
from nht_sacco.apps.integrations.models import BrandingVersion, CompanyProfile, NumberSequence
from nht_sacco.apps.integrations.validators import validate_company_logo
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.payments.models import Payment, PaymentMethod, PaymentStatus, Receipt
from nht_sacco.apps.reports.services import ReportExportService
from nht_sacco.apps.routes.models import Route, VehicleRouteAssignment
from nht_sacco.apps.vehicles.models import ComplianceCardStatus, Vehicle, VehicleCategory, VehicleComplianceCard, VehicleStatus
from nht_sacco.apps.vehicles.services import ComplianceCardService

User = get_user_model()


def _make_png_bytes(width=120, height=60, color=(16, 49, 92, 255)) -> bytes:
    buf = io.BytesIO()
    img = Image.new('RGBA', (width, height), color)
    img.save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture
def erp_bundle(db):
    super1 = User.objects.create_user(
        username='s16_super1',
        email='s16_super1@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.SUPER_ADMIN,
        is_superuser=True,
        is_staff=True,
    )
    secretary = User.objects.create_user(
        username='s16_secretary',
        email='s16_sec@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.SECRETARY,
        is_staff=True,
    )
    compliance = User.objects.create_user(
        username='s16_compliance',
        email='s16_comp@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.COMPLIANCE_OFFICER,
        is_staff=True,
    )
    treasurer = User.objects.create_user(
        username='s16_treasurer',
        email='s16_treas@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.TREASURER,
        is_staff=True,
    )
    member_user = User.objects.create_user(
        username='s16_member1',
        email='s16_m1@northernhighways.co.ke',
        password='StrongPassword123!',
        phone_number='+254712345601',
        national_id='33445566',
        role=UserRole.MEMBER,
    )
    unlinked_member = User.objects.create_user(
        username='s16_unlinked',
        email='s16_unlinked@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.MEMBER,
    )
    driver_user = User.objects.create_user(
        username='s16_driver',
        email='s16_drv@northernhighways.co.ke',
        password='StrongPassword123!',
        role=UserRole.DRIVER,
    )
    member = Member.objects.create(
        user=member_user,
        membership_number='NHT-MBR-2026-8001',
        first_name='Amina',
        last_name='Mohamed',
        national_id='33445566',
        phone_number='+254712345601',
        email='s16_m1@northernhighways.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Hassan Mohamed',
        next_of_kin_relation='Brother',
        next_of_kin_phone='+254712345602',
    )
    route = Route.objects.create(
        route_code='RT-S16',
        name='Isiolo - Marsabit Express',
        origin='Isiolo',
        destination='Marsabit',
        distance_km=270,
        is_active=True,
    )
    vehicle = Vehicle.objects.create(
        registration_number='KDS 160A',
        chassis_number='CHS-S16-160',
        engine_number='ENG-S16-160',
        make='Toyota',
        model='HiAce',
        year_of_manufacture=2023,
        category=VehicleCategory.MATATU_14,
        carrying_capacity=14,
        current_owner=member,
        status=VehicleStatus.ACTIVE,
    )
    VehicleRouteAssignment.objects.create(
        vehicle=vehicle,
        route=route,
        road_service_license='RSL-S16-01',
        is_active=True,
        authorized_by=secretary,
    )
    return {
        'super1': super1,
        'secretary': secretary,
        'compliance': compliance,
        'treasurer': treasurer,
        'member_user': member_user,
        'unlinked_member': unlinked_member,
        'driver_user': driver_user,
        'member': member,
        'route': route,
        'vehicle': vehicle,
    }


@pytest.mark.django_db
class TestUnifiedMaterialUIAndTemplates:
    def test_unified_mui_across_interfaces_and_legacy_css_removed(self, client, erp_bundle):
        assert not os.path.exists('static/css/nht_brand.css')

        # Public login & SPA shell use Material UI v5 without Bootstrap/Tailwind
        for url in [reverse('accounts:login'), '/app/']:
            html_body = client.get(url).content.decode('utf-8')
            assert 'bootstrap.min' not in html_body.lower()
            assert 'cdn.jsdelivr.net/npm/bootstrap' not in html_body.lower()
            assert 'tailwindcss' not in html_body.lower()
            assert '@mui/material' in html_body

        # Staff views (operations dashboard, reports, settings, Django admin)
        client.force_login(erp_bundle['super1'])
        for url in [
            reverse('accounts:dashboard'),
            reverse('reports:dashboard'),
            reverse('integrations:settings_index'),
            '/admin/',
        ]:
            resp = client.get(url)
            assert resp.status_code == 200
            body = resp.content.decode('utf-8')
            assert 'bootstrap.min' not in body.lower()
            assert 'cdn.jsdelivr.net/npm/bootstrap' not in body.lower()
            assert 'tailwindcss' not in body.lower()
            assert 'material-ui' in body.lower() or 'mui_unified.css' in body or 'admin_theme.css' in body

        # Member portal uses unified Material UI
        client.force_login(erp_bundle['member_user'])
        for url in [
            reverse('portal:dashboard'),
            reverse('portal:vehicles'),
            reverse('portal:vehicle_card', kwargs={'vehicle_id': erp_bundle['vehicle'].pk}),
        ]:
            resp = client.get(url)
            assert resp.status_code == 200
            body = resp.content.decode('utf-8')
            assert 'bootstrap.min' not in body.lower()
            assert 'mui_unified.css' in body


@pytest.mark.django_db
class TestStaffMemberSeparationAndSuperAdminControls:
    def test_staff_and_member_listings_are_strictly_separated(self, client, erp_bundle):
        client.force_login(erp_bundle['super1'])

        staff_res = client.get('/api/v1/staff/')
        assert staff_res.status_code == 200
        staff_usernames = {u['username'] for u in staff_res.json()['results']}
        assert 's16_super1' in staff_usernames
        assert 's16_secretary' in staff_usernames
        assert 's16_member1' not in staff_usernames
        assert 's16_driver' not in staff_usernames

        # Staff endpoint rejects creating MEMBER or DRIVER accounts
        bad_staff = client.post('/api/v1/staff/', {
            'username': 'bad_member_via_staff',
            'email': 'bad_m@northernhighways.co.ke',
            'first_name': 'Bad',
            'last_name': 'User',
            'role': UserRole.MEMBER,
            'password': 'StrongPassword123!',
        }, content_type='application/json')
        assert bad_staff.status_code == 400

        # Assigning MEMBER role through /api/v1/staff/ is blocked
        bad_role = client.post(
            f"/api/v1/staff/{erp_bundle['secretary'].pk}/assign_role/",
            {'role': UserRole.MEMBER},
            content_type='application/json',
        )
        assert bad_role.status_code == 400

        # Creating a member via /api/v1/members/ never grants staff or superuser privileges
        mem_res = client.post('/api/v1/members/', {
            'first_name': 'Halima',
            'last_name': 'Wario',
            'national_id': '44556677',
            'phone_number': '+254712345699',
            'email': 'halima.wario@northernhighways.co.ke',
            'county': 'Isiolo',
            'category': MembershipCategory.INDIVIDUAL_OPERATOR,
            'next_of_kin_name': 'Juma Wario',
            'next_of_kin_relation': 'Spouse',
            'next_of_kin_phone': '+254712345698',
        }, content_type='application/json')
        assert mem_res.status_code == 201
        created_member = Member.objects.get(pk=mem_res.json()['id'])
        assert created_member.user.role == UserRole.MEMBER
        assert created_member.user.is_staff is False
        assert created_member.user.is_superuser is False

    def test_super_admin_escalation_and_last_super_admin_protection(self, client, erp_bundle):
        # Non-super-admin staff cannot access /api/v1/staff/ or grant SUPER_ADMIN
        client.force_login(erp_bundle['secretary'])
        assert client.get('/api/v1/staff/').status_code == 403
        assert client.post(
            f"/api/v1/staff/{erp_bundle['secretary'].pk}/assign_role/",
            {'role': UserRole.SUPER_ADMIN},
            content_type='application/json',
        ).status_code == 403

        # Django Admin UserAdmin blocks ordinary staff from granting SUPER_ADMIN or deleting last Super Admin
        rf = RequestFactory()
        user_admin = admin.site._registry[User]
        req_sec = rf.post('/admin/accounts/user/')
        req_sec.user = erp_bundle['secretary']
        target_sec = User.objects.get(pk=erp_bundle['secretary'].pk)
        with pytest.raises(PermissionDenied):
            target_sec.role = UserRole.SUPER_ADMIN
            user_admin.save_model(req_sec, target_sec, form=None, change=True)

        # Super Admin cannot demote, deactivate, or delete the last active Super Admin
        client.force_login(erp_bundle['super1'])
        demote_res = client.post(
            f"/api/v1/staff/{erp_bundle['super1'].pk}/assign_role/",
            {'role': UserRole.CHAIRMAN},
            content_type='application/json',
        )
        assert demote_res.status_code == 400

        del_res = client.delete(f"/api/v1/staff/{erp_bundle['super1'].pk}/")
        assert del_res.status_code == 400

        req_sup = rf.post('/admin/accounts/user/')
        req_sup.user = erp_bundle['super1']
        with pytest.raises(PermissionDenied):
            user_admin.delete_model(req_sup, erp_bundle['super1'])

        # Account recovery & activity endpoints
        rec_res = client.post(
            f"/api/v1/staff/{erp_bundle['secretary'].pk}/initiate_recovery/",
            {'send_email': False},
            content_type='application/json',
        )
        assert rec_res.status_code == 200
        erp_bundle['secretary'].refresh_from_db()
        assert erp_bundle['secretary'].must_change_password is True

        act_res = client.get(f"/api/v1/staff/{erp_bundle['secretary'].pk}/activity/")
        assert act_res.status_code == 200
        assert 'login_history' in act_res.json()
        assert 'audit_logs' in act_res.json()

    def test_unlinked_member_cannot_enumerate_other_records(self, client, erp_bundle):
        client.force_login(erp_bundle['unlinked_member'])
        for ep in [
            '/api/v1/members/',
            '/api/v1/vehicles/',
            '/api/v1/compliance-cards/',
            '/api/v1/documents/',
            '/api/v1/invoices/',
            '/api/v1/payments/',
            '/api/v1/receipts/',
            '/api/v1/incidents/',
        ]:
            res = client.get(ep)
            assert res.status_code in (200, 403)
            if res.status_code == 200:
                payload = res.json()
                items = payload.get('results', payload)
                assert items == []


@pytest.mark.django_db
class TestConcurrencySafeNumberSequence:
    def test_membership_number_seeds_above_existing_gaps_and_handles_race(self, erp_bundle):
        year = timezone.now().year
        # Pre-existing record ends in 8001 (from erp_bundle fixture).
        # Naive count()+1 would generate 0002; NumberSequence must seed from max (8001) -> 8002.
        num1 = Member.generate_membership_number()
        assert num1 == f"NHT-MBR-{year}-8002"

        # Verify monotonic uniqueness across rapid sequential allocations
        allocated = [Member.generate_membership_number() for _ in range(15)]
        assert len(set(allocated)) == 15
        assert allocated[0] == f"NHT-MBR-{year}-8003"
        assert allocated[-1] == f"NHT-MBR-{year}-8017"

        # Simulate IntegrityError race on initial NumberSequence creation:
        # Row already committed by concurrent worker before our select_for_update().create()
        from django.db import IntegrityError
        pre_seq = NumberSequence.objects.create(prefix='NHT-RACE', year=year, last_number=1)
        orig_filter = NumberSequence.objects.select_for_update

        class FakeFirstMissing:
            def __init__(self, qs):
                self._qs = qs

            def filter(self, *args, **kwargs):
                self._filtered = self._qs.filter(*args, **kwargs)
                return self

            def first(self):
                return None

            def get(self, *args, **kwargs):
                return self._qs.get(*args, **kwargs)

        with patch.object(NumberSequence.objects, 'select_for_update', side_effect=lambda: FakeFirstMissing(orig_filter())):
            raced = NumberSequence.next_number(prefix='NHT-RACE', year=year)
            assert raced == f"NHT-RACE-{year}-0002"
        pre_seq.refresh_from_db()
        assert pre_seq.last_number == 2


@pytest.mark.django_db
class TestVehicleComplianceCardAndQRSecurity:
    def test_compliance_card_lifecycle_and_public_verification_outcomes(self, client, erp_bundle):
        cache.clear()
        client.force_login(erp_bundle['compliance'])
        vehicle = erp_bundle['vehicle']

        # 1. Issue compliance card via API
        issue_res = client.post('/api/v1/compliance-cards/', {
            'vehicle': str(vehicle.pk),
            'fleet_number': 'FLT-160',
            'expiry_date': (timezone.localdate() + timedelta(days=180)).isoformat(),
        }, content_type='application/json')
        assert issue_res.status_code == 201
        card_data = issue_res.json()
        card = VehicleComplianceCard.objects.get(pk=card_data['id'])
        raw_token = ComplianceCardService.decrypt_token(card)
        assert len(raw_token) >= 32
        assert card.token_hash != raw_token
        assert card.token_hash == VehicleComplianceCard.hash_token(raw_token)
        assert card_data['verify_url'].startswith('https://nhtsms.bagovi.com/verify/compliance/')

        # Download branded compliance card PDF
        pdf_res = client.get(f"/api/v1/compliance-cards/{card.pk}/download_pdf/")
        assert pdf_res.status_code == 200
        assert pdf_res['Content-Type'] == 'application/pdf'
        assert pdf_res.content.startswith(b'%PDF')

        # 2. Public verification works anonymously and leaks ZERO PII
        client.logout()
        verify_url = f"/verify/compliance/{raw_token}/"
        v_res = client.get(verify_url)
        assert v_res.status_code == 200
        assert 'no-store' in v_res['Cache-Control']
        v_body = v_res.content.decode('utf-8')
        assert 'VALID' in v_body
        assert 'KDS 160A' in v_body
        assert card.certificate_number in v_body
        # Zero PII assertions (no national ID, phone, email, or owner personal info)
        assert '33445566' not in v_body
        assert '+254712345601' not in v_body
        assert 's16_m1@northernhighways.co.ke' not in v_body
        assert 'Amina Mohamed' not in v_body

        # 3. SUSPEND outcome
        client.force_login(erp_bundle['compliance'])
        client.post(f"/api/v1/compliance-cards/{card.pk}/suspend/", {'reason': 'Inspection hold'}, content_type='application/json')
        client.logout()
        s_body = client.get(verify_url).content.decode('utf-8')
        assert 'SUSPENDED' in s_body

        # Reinstate back to VALID
        client.force_login(erp_bundle['compliance'])
        client.post(f"/api/v1/compliance-cards/{card.pk}/reinstate/", {}, content_type='application/json')

        # 4. ROTATE QR invalidates old token immediately
        rot_res = client.post(f"/api/v1/compliance-cards/{card.pk}/regenerate_qr/", {}, content_type='application/json')
        assert rot_res.status_code == 200
        card.refresh_from_db()
        new_token = ComplianceCardService.decrypt_token(card)
        assert new_token != raw_token
        client.logout()
        assert client.get(verify_url).status_code == 404
        assert 'INVALID' in client.get(verify_url).content.decode('utf-8')
        new_verify_url = f"/verify/compliance/{new_token}/"
        assert client.get(new_verify_url).status_code == 200
        assert 'VALID' in client.get(new_verify_url).content.decode('utf-8')

        # 5. RENEW supersedes old card immediately
        client.force_login(erp_bundle['compliance'])
        ren_res = client.post(f"/api/v1/compliance-cards/{card.pk}/renew/", {}, content_type='application/json')
        assert ren_res.status_code == 201
        new_card = VehicleComplianceCard.objects.get(pk=ren_res.json()['id'])
        new_card_token = ComplianceCardService.decrypt_token(new_card)
        client.logout()
        sup_body = client.get(new_verify_url).content.decode('utf-8')
        assert 'SUPERSEDED' in sup_body

        # 6. REVOKE invalidates new card immediately
        client.force_login(erp_bundle['compliance'])
        client.post(f"/api/v1/compliance-cards/{new_card.pk}/revoke/", {'reason': 'Permit withdrawn'}, content_type='application/json')
        client.logout()
        rev_body = client.get(f"/verify/compliance/{new_card_token}/").content.decode('utf-8')
        assert 'REVOKED' in rev_body

        # 7. EXPIRED outcome
        client.force_login(erp_bundle['compliance'])
        exp_res = client.post('/api/v1/compliance-cards/', {
            'vehicle': str(vehicle.pk),
            'expiry_date': (timezone.localdate() - timedelta(days=1)).isoformat(),
        }, content_type='application/json')
        assert exp_res.status_code == 201
        exp_card = VehicleComplianceCard.objects.get(pk=exp_res.json()['id'])
        exp_token = ComplianceCardService.decrypt_token(exp_card)
        client.logout()
        exp_body = client.get(f"/verify/compliance/{exp_token}/").content.decode('utf-8')
        assert 'EXPIRED' in exp_body

        # 8. INVALID token & Rate limit (429)
        bad_res = client.get('/verify/compliance/non-existent-fake-token-xyz/')
        assert bad_res.status_code == 404
        assert 'INVALID' in bad_res.content.decode('utf-8')

        cache.set('nht:qr_verify_rl:127.0.0.1', 60, 60)
        rl_res = client.get(f"/verify/compliance/{exp_token}/", REMOTE_ADDR='127.0.0.1')
        assert rl_res.status_code == 429


@pytest.mark.django_db
class TestCentralCompanyBrandingAndDocumentVersioning:
    def test_logo_validation_rejects_malicious_and_invalid_files(self):
        # Reject SVG
        svg = SimpleUploadedFile('logo.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', content_type='image/svg+xml')
        with pytest.raises(ValidationError):
            validate_company_logo(svg)

        # Reject fake PNG (invalid magic bytes)
        fake_png = SimpleUploadedFile('evil.png', b'#!/bin/sh\nrm -rf /', content_type='image/png')
        with pytest.raises(ValidationError):
            validate_company_logo(fake_png)

        # Reject tiny image (<32x32)
        tiny_png = SimpleUploadedFile('tiny.png', _make_png_bytes(16, 16), content_type='image/png')
        with pytest.raises(ValidationError):
            validate_company_logo(tiny_png)

        # Accept valid PNG
        good_png = SimpleUploadedFile('good.png', _make_png_bytes(120, 60), content_type='image/png')
        validate_company_logo(good_png)

    def test_branding_upload_embedding_fallback_and_immutable_history(self, client, erp_bundle, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path / 'public_media')
        # Non-Super-Admin cannot modify CompanyProfile
        client.force_login(erp_bundle['secretary'])
        assert client.patch('/settings/api/v1/company-profile/', {'trading_name': 'Hacked'}, content_type='application/json').status_code == 403

        # 1. Text fallback works when no logo is uploaded
        profile = CompanyProfile.get_active()
        assert not (profile.logo and profile.logo.name)
        fallback_pdf = ReportExportService.generate_compliance_pdf()
        assert fallback_pdf.startswith(b'%PDF')

        # 2. Super Admin uploads Logo v1 (Blue) + Trading Name v1
        from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart
        client.force_login(erp_bundle['super1'])
        logo_v1 = SimpleUploadedFile('logo_v1.png', _make_png_bytes(140, 70, (16, 49, 92, 255)), content_type='image/png')
        up1 = client.patch(
            '/settings/api/v1/company-profile/',
            encode_multipart(BOUNDARY, {
                'trading_name': 'NHT SACCO Alpha Branding',
                'legal_name': 'NHT SACCO Alpha Legal Ltd',
                'logo': logo_v1,
                'change_notes': 'Initial official logo v1',
            }),
            content_type=MULTIPART_CONTENT,
        )
        assert up1.status_code == 200
        v1_num = up1.json()['current_version']
        assert up1.json()['logo_url']

        # Logo asset preview streams PNG
        asset_res = client.get('/settings/api/v1/company-profile/logo-asset/')
        assert asset_res.status_code == 200
        assert asset_res['Content-Type'] == 'image/png'

        # 3. Issue Invoice, Receipt, Membership Certificate, and Compliance Card under v1
        svc = ServiceItem.objects.create(code='S16-FEE', name='SACCO Fee', category='MEMBERSHIP', is_statutory=False)
        inv1 = Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            member=erp_bundle['member'],
            vehicle=erp_bundle['vehicle'],
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
        )
        InvoiceItem.objects.create(invoice=inv1, service_item=svc, description='Annual Fee', unit_price=Decimal('1000.00'), quantity=1)
        inv1.recalculate_totals()
        pay1 = Payment.objects.create(
            payment_reference=Payment.generate_payment_reference(),
            invoice=inv1,
            member=erp_bundle['member'],
            method=PaymentMethod.CASH,
            amount=Decimal('1000.00'),
            idempotency_key='S16-PAY-1',
            status=PaymentStatus.SUCCESS,
            confirmed_at=timezone.now(),
        )
        rec1 = Receipt.objects.create(
            receipt_number=Receipt.generate_receipt_number(),
            payment=pay1,
            issued_by=erp_bundle['treasurer'],
        )
        assert inv1.branding_version.version_number == v1_num
        assert rec1.branding_version.version_number == v1_num

        # Capture v1 membership certificate
        cert_v1_res = client.get(f"/api/v1/members/{erp_bundle['member'].pk}/certificate_pdf/")
        assert cert_v1_res.status_code == 200
        assert cert_v1_res.content.startswith(b'%PDF')
        erp_bundle['member'].refresh_from_db()
        assert erp_bundle['member'].branding_version.version_number == v1_num

        # Excel export embeds actual proportional logo image & preserves SUM formulas
        xlsx_bytes = ReportExportService.generate_financial_excel()
        wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
        assert len(wb['Invoices']._images) == 1
        assert len(wb['Receipts & Payments']._images) == 1
        # Verify SUM formula exists in Invoices sheet
        formulas = [
            cell.value
            for row in wb['Invoices'].iter_rows()
            for cell in row
            if isinstance(cell.value, str) and cell.value.startswith('=SUM(')
        ]
        assert len(formulas) >= 1

        # 4. Super Admin replaces logo & changes trading name -> Branding v2
        logo_v2 = SimpleUploadedFile('logo_v2.png', _make_png_bytes(160, 80, (255, 138, 0, 255)), content_type='image/png')
        up2 = client.patch(
            '/settings/api/v1/company-profile/',
            encode_multipart(BOUNDARY, {
                'trading_name': 'NHT SACCO Beta Rebrand',
                'legal_name': 'NHT SACCO Beta Legal Ltd',
                'logo': logo_v2,
                'change_notes': 'Rebranded logo v2',
            }),
            content_type=MULTIPART_CONTENT,
        )
        assert up2.status_code == 200
        v2_num = up2.json()['current_version']
        assert v2_num > v1_num

        # 5. Historical v1 documents STILL retain v1 branding, while newly issued documents use v2
        old_inv_ctx = DocumentBrandingService.get_branding_context(branding_version=inv1.branding_version)
        assert old_inv_ctx['trading_name'] == 'NHT SACCO Alpha Branding'
        assert old_inv_ctx['version_number'] == v1_num

        old_rec_html = client.get(reverse('payments:receipt_detail', kwargs={'pk': rec1.pk})).content.decode('utf-8')
        assert 'NHT SACCO Alpha Branding' in old_rec_html
        assert f"version={v1_num}" in old_rec_html

        inv2 = Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            member=erp_bundle['member'],
            vehicle=erp_bundle['vehicle'],
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
        )
        new_inv_ctx = DocumentBrandingService.get_branding_context(branding_version=inv2.branding_version)
        assert new_inv_ctx['trading_name'] == 'NHT SACCO Beta Rebrand'
        assert new_inv_ctx['version_number'] == v2_num

        # Formal reissue updates membership certificate branding to v2
        reissue_res = client.get(f"/api/v1/members/{erp_bundle['member'].pk}/certificate_pdf/?reissue=1")
        assert reissue_res.status_code == 200
        erp_bundle['member'].refresh_from_db()
        assert erp_bundle['member'].branding_version.version_number == v2_num

        # Branding version history endpoint lists v1 and v2
        vers_res = client.get('/settings/api/v1/company-profile/versions/')
        assert vers_res.status_code == 200
        assert len(vers_res.json()) >= 2

        # Delete logo removes active logo cleanly and falls back gracefully
        del_logo = client.delete('/settings/api/v1/company-profile/logo/?type=primary')
        assert del_logo.status_code == 200
        assert del_logo.json()['logo_url'] == ''
