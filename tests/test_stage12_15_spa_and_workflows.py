import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from nht_sacco.apps.drivers.models import Driver, DriverAssignment, DriverStatus
from nht_sacco.apps.documents.models import DocumentType, Document, DocumentCategory, VerificationStatus
from nht_sacco.apps.compliance.models import ComplianceAlert
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.billing.models import ServiceItem, ServicePrice, Invoice, InvoiceItem, InvoiceStatus
from nht_sacco.apps.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    Receipt,
    ManualPaymentVoucher,
    ReconciliationException,
)
from nht_sacco.apps.payments.reconciliation import PaymentReconciliationService
from nht_sacco.apps.accounting.models import Account, AccountType, FinancialPeriod, Expense
from nht_sacco.apps.accounting.services import AccountingService
from nht_sacco.apps.integrations.models import SystemConfiguration, ConfigCategory, ConfigDataType
from nht_sacco.apps.integrations.services import ConfigurationService
from nht_sacco.apps.reports.services import ReportExportService

User = get_user_model()


@pytest.fixture
def roles_bundle(db):
    def _mk(username, role, **extra):
        return User.objects.create_user(
            username=username,
            email=f"{username}@nhttransporters.co.ke",
            password="StrongPassword123!",
            role=role,
            **extra,
        )

    admin = _mk('s12_admin', UserRole.SUPER_ADMIN, is_superuser=True, is_staff=True)
    chairman = _mk('s12_chairman', UserRole.CHAIRMAN)
    treasurer = _mk('s12_treasurer', UserRole.TREASURER)
    accountant = _mk('s12_accountant', UserRole.ACCOUNTANT)
    compliance = _mk('s12_compliance', UserRole.COMPLIANCE_OFFICER)
    renewal = _mk('s12_renewal', UserRole.RENEWAL_OFFICER)
    field_off = _mk('s12_field', UserRole.FIELD_OFFICER)
    auditor = _mk('s12_auditor', UserRole.AUDITOR)
    member_user = _mk('s12_member', UserRole.MEMBER)
    other_member_user = _mk('s12_member2', UserRole.MEMBER)
    driver_user = _mk('s12_driver', UserRole.DRIVER)

    m1 = Member.objects.create(
        user=member_user,
        membership_number='NHT-MBR-2026-9001',
        first_name='Ali',
        last_name='Hassan',
        national_id='90010001',
        phone_number='+254799001001',
        email='m9001@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin One',
        next_of_kin_relation='Spouse',
        next_of_kin_phone='+254799001002',
    )
    m2 = Member.objects.create(
        user=other_member_user,
        membership_number='NHT-MBR-2026-9002',
        first_name='Halima',
        last_name='Abdi',
        national_id='90010002',
        phone_number='+254799002001',
        email='m9002@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin Two',
        next_of_kin_relation='Sister',
        next_of_kin_phone='+254799002002',
    )
    vehicle = Vehicle.objects.create(
        registration_number='KZZ 901A',
        chassis_number='CHS-901A',
        engine_number='ENG-901A',
        make='Toyota',
        model='HiAce',
        year_of_manufacture=2022,
        category=VehicleCategory.MATATU_14,
        carrying_capacity=14,
        current_owner=m1,
        status=VehicleStatus.ACTIVE,
    )
    driver = Driver.objects.create(
        user=driver_user,
        full_name='Yusuf Jama',
        national_id='90010099',
        phone_number='+254799009099',
        driving_license_number='DL-9001',
        dl_expiry_date=timezone.localdate() + timedelta(days=120),
        psv_badge_number='PSV-9001',
        psv_badge_expiry=timezone.localdate() + timedelta(days=120),
        emergency_contact_name='Amina',
        emergency_contact_phone='+254799009100',
        status=DriverStatus.ACTIVE,
    )
    DriverAssignment.objects.create(driver=driver, vehicle=vehicle, is_current=True, assigned_by=admin)

    Account.objects.get_or_create(code='1020', defaults={'name': 'M-Pesa Collections', 'type': AccountType.ASSET})
    Account.objects.get_or_create(code='1030', defaults={'name': 'Bank Account', 'type': AccountType.ASSET})
    Account.objects.get_or_create(code='1100', defaults={'name': 'Accounts Receivable', 'type': AccountType.ASSET})
    Account.objects.get_or_create(code='2020', defaults={'name': 'Statutory Pass-Through', 'type': AccountType.LIABILITY})
    Account.objects.get_or_create(code='4020', defaults={'name': 'SACCO Service Revenue', 'type': AccountType.REVENUE})
    Account.objects.get_or_create(code='5010', defaults={'name': 'Office & Admin Expense', 'type': AccountType.EXPENSE})

    return {
        'admin': admin,
        'chairman': chairman,
        'treasurer': treasurer,
        'accountant': accountant,
        'compliance': compliance,
        'renewal': renewal,
        'field': field_off,
        'auditor': auditor,
        'member_user': member_user,
        'other_member_user': other_member_user,
        'driver_user': driver_user,
        'member1': m1,
        'member2': m2,
        'vehicle': vehicle,
        'driver': driver,
    }


@pytest.mark.django_db
class TestRegressionsAndCompliance:
    def test_30_day_compliance_alert_triggered(self, roles_bundle):
        dt = DocumentType.objects.create(
            name='NTSA 30-Day Inspection',
            category=DocumentCategory.INSPECTION,
            is_mandatory_for_vehicle=True,
            reminder_thresholds=[30, 14, 7, 3, 0],
        )
        today = timezone.localdate()
        Document.objects.create(
            document_type=dt,
            vehicle=roles_bundle['vehicle'],
            reference_number='INSP-30D-01',
            issue_date=today - timedelta(days=150),
            expiry_date=today + timedelta(days=30),
            file=SimpleUploadedFile('insp30.pdf', b'%PDF-1.4 test'),
            status=VerificationStatus.VERIFIED,
        )
        res = ComplianceService.run_daily_compliance_scan()
        assert res['alerts_created'] >= 1
        assert ComplianceAlert.objects.filter(
            vehicle=roles_bundle['vehicle'],
            alert_type=ComplianceAlert.AlertType.UPCOMING_EXPIRY,
            days_remaining=30,
        ).exists()

    def test_portal_invoice_receipt_renewal_and_excel_export(self, client, roles_bundle):
        svc = ServiceItem.objects.create(
            code='RNW-TEST',
            name='RSL Renewal Fee',
            category='RENEWAL',
            is_statutory=True,
        )
        ServicePrice.objects.create(service_item=svc, amount=Decimal('1500.00'))
        inv = Invoice.objects.create(
            invoice_number='NHT-INV-2026-9901',
            member=roles_bundle['member1'],
            vehicle=roles_bundle['vehicle'],
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
        )
        InvoiceItem.objects.create(
            invoice=inv,
            service_item=svc,
            description='RSL Renewal Statutory Fee',
            unit_price=Decimal('1500.00'),
            quantity=1,
        )
        inv.recalculate_totals()

        pay = Payment.objects.create(
            payment_reference='NHT-PAY-2026-9901',
            invoice=inv,
            member=roles_bundle['member1'],
            method=PaymentMethod.MPESA,
            amount=Decimal('1500.00'),
            idempotency_key='IDEMP-9901',
            status=PaymentStatus.INITIATED,
        )
        AccountingService.record_payment_settlement(
            payment=pay,
            amount=Decimal('1500.00'),
            provider_transaction_id='MPE9901XYZ',
            user=roles_bundle['treasurer'],
        )

        # Portal detail, receipts, and sequential renewals
        client.force_login(roles_bundle['member_user'])
        res_inv = client.get(reverse('portal:invoice_detail', kwargs={'invoice_id': inv.pk}))
        assert res_inv.status_code == 200
        assert 'RSL Renewal Fee' in res_inv.content.decode('utf-8')

        res_rec = client.get(reverse('portal:receipts'))
        assert res_rec.status_code == 200
        assert '1500.00' in res_rec.content.decode('utf-8')

        dt = DocumentType.objects.create(name='Insurance 99', category=DocumentCategory.INSURANCE, is_mandatory_for_vehicle=True)
        for _ in range(2):
            r = client.post(reverse('portal:renewal_apply'), {
                'vehicle_id': str(roles_bundle['vehicle'].pk),
                'document_type_id': str(dt.pk),
                'notes': 'Sequential test',
            })
            assert r.status_code == 302
        assert RenewalRequest.objects.filter(member=roles_bundle['member1']).count() == 2

        # Financial Excel export works with real invoices/items/payments
        xlsx_bytes = ReportExportService.generate_financial_excel()
        assert len(xlsx_bytes) > 500


@pytest.mark.django_db
class TestElevenRoleRBACAndSPA:
    def test_least_privilege_fixes_and_driver_isolation(self, client, roles_bundle):
        # Field officer (is_staff=True) cannot export financial Excel
        client.force_login(roles_bundle['field'])
        assert client.get(reverse('reports:export_financial_excel')).status_code == 403
        assert client.get('/api/v1/accounting/reports/').status_code == 403

        # Treasurer CAN export financial Excel
        client.force_login(roles_bundle['treasurer'])
        assert client.get(reverse('reports:export_financial_excel')).status_code == 200

        # Auditor is read-only
        client.force_login(roles_bundle['auditor'])
        assert client.get('/api/v1/audit-logs/').status_code == 200
        assert client.post('/api/v1/accounts/', {'code': '9999', 'name': 'X', 'type': 'ASSET'}).status_code == 403

        # Driver role has is_staff=False, accesses driver portal, denied management endpoints
        drv_user = roles_bundle['driver_user']
        assert drv_user.is_staff is False
        client.force_login(drv_user)
        drv_res = client.get('/api/v1/driver/portal/')
        assert drv_res.status_code == 200
        assert 'KZZ 901A' in drv_res.content.decode('utf-8')
        assert client.get('/api/v1/members/').status_code == 403
        assert client.get('/api/v1/users/').status_code == 403

        # Member cannot access dashboard or other member records
        client.force_login(roles_bundle['member_user'])
        assert client.get('/api/v1/dashboard/').status_code == 403
        assert client.get('/api/v1/users/').status_code == 403

    def test_spa_shell_and_no_hardcoded_passwords(self, client, roles_bundle):
        login_html = client.get(reverse('accounts:login')).content.decode('utf-8')
        assert 'Admin@NHT2026!' not in login_html
        assert '/app/' in login_html

        spa_res = client.get('/app/')
        assert spa_res.status_code == 200
        body = spa_res.content.decode('utf-8')
        assert '@mui/material' in body
        assert 'name="csrf-token"' in body
        assert 'Admin@NHT2026!' not in body

        client.force_login(roles_bundle['driver_user'])
        me_res = client.get('/api/v1/auth/me/')
        assert me_res.status_code == 200
        payload = me_res.json()
        assert payload['authenticated'] is True
        assert payload.get('csrf_token')
        assert 'driver-portal' in payload['allowed_sections']

        # Verify CSRF-enforced SPA login & logout work with rotated csrf_token
        from django.test import Client as CsrfClient
        csrf_client = CsrfClient(enforce_csrf_checks=True)
        pre_me = csrf_client.get('/api/v1/auth/me/').json()
        login_res = csrf_client.post(
            '/api/v1/auth/login/',
            {'username': roles_bundle['driver_user'].username, 'password': 'StrongPassword123!'},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=pre_me['csrf_token'],
        )
        assert login_res.status_code == 200
        rotated_token = login_res.json().get('csrf_token')
        assert rotated_token
        logout_res = csrf_client.post(
            '/api/v1/auth/logout/',
            {},
            content_type='application/json',
            HTTP_X_CSRFTOKEN=rotated_token,
        )
        assert logout_res.status_code == 200
        assert logout_res.json().get('csrf_token')


@pytest.mark.django_db
class TestStage12FinancialIntegrityAndChangeRequests:
    def test_renewal_auto_paid_reconciliation_and_statements(self, client, roles_bundle):
        dt = DocumentType.objects.create(name='KeNHA Permit 12', category=DocumentCategory.KENHA_PERMIT, is_mandatory_for_vehicle=True)
        svc = ServiceItem.objects.create(code='RNW-12', name='KeNHA Renewal', category='RENEWAL', is_statutory=True)
        ServicePrice.objects.create(service_item=svc, amount=Decimal('2000.00'))
        inv = Invoice.objects.create(
            invoice_number='NHT-INV-2026-9912',
            member=roles_bundle['member1'],
            vehicle=roles_bundle['vehicle'],
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
        )
        InvoiceItem.objects.create(invoice=inv, service_item=svc, description='KeNHA Permit', unit_price=Decimal('2000.00'), quantity=1)
        inv.recalculate_totals()
        AccountingService.post_invoice_issuance(inv, user=roles_bundle['treasurer'])

        rnw = RenewalRequest.objects.create(
            member=roles_bundle['member1'],
            vehicle=roles_bundle['vehicle'],
            document_type=dt,
            invoice=inv,
            status=RenewalStatus.INVOICED,
        )

        # Clean payment settles invoice AND transitions renewal to PAID
        p_ok = Payment.objects.create(
            payment_reference='NHT-PAY-2026-9912',
            invoice=inv,
            member=roles_bundle['member1'],
            method=PaymentMethod.MPESA,
            amount=Decimal('2000.00'),
            idempotency_key='IDEMP-9912',
            status=PaymentStatus.INITIATED,
        )
        AccountingService.record_payment_settlement(p_ok, Decimal('2000.00'), 'MPESA9912', user=roles_bundle['treasurer'])
        rnw.refresh_from_db()
        assert rnw.status == RenewalStatus.PAID

        # Add a stale INITIATED payment and run reconciliation
        Payment.objects.create(
            payment_reference='NHT-PAY-2026-9913',
            invoice=inv,
            member=roles_bundle['member1'],
            method=PaymentMethod.MPESA,
            amount=Decimal('500.00'),
            idempotency_key='IDEMP-9913',
            status=PaymentStatus.INITIATED,
        )
        run = PaymentReconciliationService.run_reconciliation(user=roles_bundle['treasurer'])
        assert run.matched_count >= 1
        assert run.exception_count >= 1
        exc = run.exceptions.filter(exception_type=ReconciliationException.ExceptionType.UNMATCHED_INITIATED).first()
        assert exc is not None
        PaymentReconciliationService.resolve_exception(exc, roles_bundle['treasurer'], 'Confirmed timeout by customer')
        exc.refresh_from_db()
        assert exc.status == ReconciliationException.Status.RESOLVED

        # Statements balance
        tb = AccountingService.get_trial_balance()
        assert tb['is_balanced'] is True
        bs = AccountingService.get_balance_sheet()
        assert bs['is_balanced'] is True
        ie = AccountingService.get_income_and_expenditure()
        assert ie['total_revenue'] >= Decimal('0.00')

        # Closed financial period rejects new postings
        today = timezone.localdate()
        period = AccountingService.get_or_create_current_period(today)
        AccountingService.close_period(period, roles_bundle['treasurer'])
        with pytest.raises(ValidationError):
            AccountingService.get_or_create_current_period(today)
        AccountingService.reopen_period(period, roles_bundle['treasurer'], 'Test cleanup')

    def test_voucher_and_config_change_request_maker_checker(self, client, roles_bundle):
        inv = Invoice.objects.create(
            invoice_number='NHT-INV-2026-9950',
            member=roles_bundle['member1'],
            vehicle=roles_bundle['vehicle'],
            issue_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('1000.00'),
        )
        # Treasurer submits voucher (Maker), cannot approve own voucher, Accountant approves (Checker)
        client.force_login(roles_bundle['treasurer'])
        v_res = client.post('/api/v1/vouchers/', {
            'invoice': str(inv.pk),
            'method': 'BANK_TRANSFER',
            'bank_slip_reference': 'SLIP-9950',
            'bank_name': 'KCB',
            'amount': '1000.00',
            'payment_date': str(timezone.localdate()),
        }, content_type='application/json')
        assert v_res.status_code == 201
        vid = v_res.json()['id']

        assert client.post(f'/api/v1/vouchers/{vid}/approve/', {}, content_type='application/json').status_code == 403

        client.force_login(roles_bundle['accountant'])
        app_res = client.post(f'/api/v1/vouchers/{vid}/approve/', {'notes': 'Bank verified'}, content_type='application/json')
        assert app_res.status_code == 200
        assert ManualPaymentVoucher.objects.get(pk=vid).status == ManualPaymentVoucher.Status.VERIFIED

        # ConfigurationChangeRequest Maker-Checker
        SystemConfiguration.objects.get_or_create(
            key='business.currency',
            defaults={
                'category': ConfigCategory.BUSINESS,
                'data_type': ConfigDataType.STRING,
                'raw_value': 'KES',
                'default_value': 'KES',
                'title': 'SACCO Currency',
            },
        )
        client.force_login(roles_bundle['admin'])
        cr_res = client.post('/settings/api/v1/change-requests/', {
            'key': 'business.currency',
            'proposed_value': 'USD',
            'justification': 'Test currency request',
        }, content_type='application/json')
        assert cr_res.status_code == 201
        cr_id = cr_res.json()['id']

        # Maker cannot self-approve
        assert client.post(f'/settings/api/v1/change-requests/{cr_id}/approve/', {}, content_type='application/json').status_code == 400

        # Chairman approves
        client.force_login(roles_bundle['chairman'])
        cr_app = client.post(f'/settings/api/v1/change-requests/{cr_id}/approve/', {'comments': 'Board approved'}, content_type='application/json')
        assert cr_app.status_code == 200
        assert ConfigurationService.get_str('business.currency') == 'USD'
