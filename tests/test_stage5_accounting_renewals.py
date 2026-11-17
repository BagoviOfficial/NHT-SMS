import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, VehicleStatus
from nht_sacco.apps.documents.models import DocumentType, Document, DocumentCategory, VerificationStatus
from nht_sacco.apps.billing.models import Invoice, InvoiceItem, ServiceItem, ServiceCategory
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.accounting.models import Account, AccountType, FinancialPeriod, JournalEntry, JournalLine, Expense
from nht_sacco.apps.accounting.services import AccountingService

User = get_user_model()

@pytest.fixture
def accounting_staff(db):
    treasurer = User.objects.create_user(
        username='treasurer_acct',
        email='treasurer_acct@nhttransporters.co.ke',
        password='TreasurerPass123!',
        role=UserRole.TREASURER
    )
    clerk = User.objects.create_user(
        username='clerk_acct',
        email='clerk_acct@nhttransporters.co.ke',
        password='ClerkPass123!',
        role=UserRole.FIELD_OFFICER
    )
    compliance_officer = User.objects.create_user(
        username='compliance_acct',
        email='compliance_acct@nhttransporters.co.ke',
        password='OfficerPass123!',
        role=UserRole.COMPLIANCE_OFFICER
    )
    return treasurer, clerk, compliance_officer

@pytest.fixture
def sample_member_vehicle(db):
    user = User.objects.create_user(
        username='renewing_member',
        email='renewing@nhttransporters.co.ke',
        password='Password123!',
        role=UserRole.MEMBER
    )
    member = Member.objects.create(
        user=user,
        membership_number='NHT-MBR-2026-8888',
        first_name='Farah',
        last_name='Idriss',
        national_id='44556677',
        phone_number='+254711998877',
        email='renewing@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin',
        next_of_kin_relation='Brother',
        next_of_kin_phone='+254711998878'
    )
    vehicle = Vehicle.objects.create(
        registration_number='KDA 707Z',
        chassis_number='CHS-707Z',
        engine_number='ENG-707Z',
        make='Toyota',
        model='HiAce',
        year_of_manufacture=2021,
        category=VehicleCategory.MATATU_14,
        carrying_capacity=14,
        current_owner=member,
        status=VehicleStatus.ACTIVE
    )
    return member, vehicle

@pytest.fixture
def chart_of_accounts(db):
    period, _ = FinancialPeriod.objects.get_or_create(
        name='TEST-FY2026',
        defaults={'start_date': date(2026, 1, 1), 'end_date': date(2026, 12, 31), 'is_closed': False}
    )
    a_cash, _ = Account.objects.get_or_create(code='1010', defaults={'name': 'Cash', 'type': AccountType.ASSET})
    a_mpesa, _ = Account.objects.get_or_create(code='1020', defaults={'name': 'M-Pesa', 'type': AccountType.ASSET})
    a_bank, _ = Account.objects.get_or_create(code='1030', defaults={'name': 'Bank', 'type': AccountType.ASSET})
    a_ar, _ = Account.objects.get_or_create(code='1100', defaults={'name': 'Accounts Receivable', 'type': AccountType.ASSET})
    a_stat, _ = Account.objects.get_or_create(code='2020', defaults={'name': 'Statutory Payable', 'type': AccountType.LIABILITY})
    a_rev, _ = Account.objects.get_or_create(code='4020', defaults={'name': 'Operations Revenue', 'type': AccountType.REVENUE})
    a_exp, _ = Account.objects.get_or_create(code='5010', defaults={'name': 'Office Expense', 'type': AccountType.EXPENSE})
    return period, a_cash, a_mpesa, a_bank, a_ar, a_stat, a_rev, a_exp


@pytest.mark.django_db
class TestDoubleEntryLedger:
    def test_balanced_entry_creation_and_balance_tracking(self, chart_of_accounts, accounting_staff):
        period, a_cash, _, a_bank, _, _, _, a_exp = chart_of_accounts
        treasurer, _, _ = accounting_staff

        entry = JournalEntry.objects.create(
            entry_number='NHT-JRN-2026-0001',
            date=date.today(),
            period=period,
            reference='REF-001',
            narration='Office equipment purchase',
            posted_by=treasurer
        )
        JournalLine.objects.create(journal_entry=entry, account=a_exp, debit=Decimal('12000.00'))
        JournalLine.objects.create(journal_entry=entry, account=a_bank, credit=Decimal('12000.00'))

        assert entry.verify_balance() is True
        assert a_exp.current_balance == Decimal('12000.00')
        assert a_bank.current_balance == Decimal('-12000.00')

    def test_unbalanced_entry_rejected(self, chart_of_accounts, accounting_staff):
        period, a_cash, _, a_bank, _, _, _, a_exp = chart_of_accounts
        treasurer, _, _ = accounting_staff

        entry = JournalEntry.objects.create(
            entry_number='NHT-JRN-2026-UNBAL',
            date=date.today(),
            period=period,
            reference='REF-UNBAL',
            narration='Unbalanced error test',
            posted_by=treasurer
        )
        JournalLine.objects.create(journal_entry=entry, account=a_exp, debit=Decimal('5000.00'))
        JournalLine.objects.create(journal_entry=entry, account=a_bank, credit=Decimal('4000.00'))

        with pytest.raises(ValidationError):
            entry.verify_balance()

    def test_posted_entry_immutability_and_reversal(self, chart_of_accounts, accounting_staff):
        period, _, _, a_bank, _, _, _, a_exp = chart_of_accounts
        treasurer, _, _ = accounting_staff

        entry = JournalEntry.objects.create(
            entry_number='NHT-JRN-2026-IMMUT',
            date=date.today(),
            period=period,
            reference='REF-IMMUT',
            narration='Original transaction',
            posted_by=treasurer,
            is_posted=True
        )
        JournalLine.objects.create(journal_entry=entry, account=a_exp, debit=Decimal('8000.00'))
        JournalLine.objects.create(journal_entry=entry, account=a_bank, credit=Decimal('8000.00'))
        entry.verify_balance()

        # 1. Direct delete must be blocked!
        with pytest.raises(ValidationError):
            entry.delete()

        # 2. Modify date/period must be blocked!
        entry.date = date.today() - timedelta(days=10)
        with pytest.raises(ValidationError):
            entry.clean()

        # 3. Formal Reversal Entry
        reversal = AccountingService.reverse_journal_entry(entry, treasurer, reason='Erroneous disbursement')
        assert reversal.is_reversal is True
        assert reversal.reverses_entry == entry
        assert reversal.verify_balance() is True

        # Balances should neutralize to 0.00
        assert a_exp.current_balance == Decimal('0.00')
        assert a_bank.current_balance == Decimal('0.00')

    def test_closed_financial_period_blocks_posting(self, chart_of_accounts, accounting_staff):
        period, _, _, a_bank, _, _, _, a_exp = chart_of_accounts
        treasurer, _, _ = accounting_staff

        # Close period
        period.is_closed = True
        period.save()

        entry = JournalEntry(
            entry_number='NHT-JRN-2026-CLOSED',
            date=date.today(),
            period=period,
            reference='REF-CLOSED',
            narration='Entry in closed period',
            posted_by=treasurer
        )
        with pytest.raises(ValidationError):
            entry.clean()

    def test_trial_balance_calculation(self, chart_of_accounts, accounting_staff):
        period, _, a_mpesa, _, a_ar, a_stat, a_rev, _ = chart_of_accounts
        treasurer, _, _ = accounting_staff

        # Post balanced invoice journal
        e1 = JournalEntry.objects.create(
            entry_number='NHT-JRN-2026-TB1',
            date=date.today(),
            period=period,
            reference='INV-TB1',
            narration='Invoice test',
            posted_by=treasurer
        )
        JournalLine.objects.create(journal_entry=e1, account=a_ar, debit=Decimal('7000.00'))
        JournalLine.objects.create(journal_entry=e1, account=a_rev, credit=Decimal('5000.00'))
        JournalLine.objects.create(journal_entry=e1, account=a_stat, credit=Decimal('2000.00'))
        e1.verify_balance()

        tb = AccountingService.get_trial_balance()
        assert tb['is_balanced'] is True
        assert tb['total_debits'] == tb['total_credits']


@pytest.mark.django_db
class TestDocumentRenewalLifecycle:
    def test_full_renewal_workflow(self, sample_member_vehicle, accounting_staff):
        member, vehicle = sample_member_vehicle
        treasurer, clerk, compliance_officer = accounting_staff

        doc_type = DocumentType.objects.create(
            name='KeNHA Renewal Test Permit',
            category=DocumentCategory.KENHA_PERMIT,
            is_mandatory_for_vehicle=True
        )
        old_doc = Document.objects.create(
            document_type=doc_type,
            vehicle=vehicle,
            reference_number='KENHA-OLD-001',
            issue_date=date.today() - timedelta(days=360),
            expiry_date=date.today() + timedelta(days=5),
            file=SimpleUploadedFile("old.pdf", b"old permit"),
            status=VerificationStatus.VERIFIED
        )

        # 1. Member submits renewal
        renewal = RenewalRequest.objects.create(
            request_number=RenewalRequest.generate_request_number(),
            member=member,
            vehicle=vehicle,
            document_type=doc_type,
            current_document=old_doc,
            status=RenewalStatus.SUBMITTED,
            notes='Urgent renewal for highway permit.'
        )
        assert renewal.status == RenewalStatus.SUBMITTED

        # 2. Officer reviews & generates invoice
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-RNW01',
            member=member,
            vehicle=vehicle,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('4500.00')
        )
        renewal.mark_reviewed(clerk, invoice)
        assert renewal.status == RenewalStatus.INVOICED
        assert renewal.invoice == invoice

        # 3. Payment settlement
        invoice.allocate_payment(Decimal('4500.00'))
        renewal.mark_paid()
        assert renewal.status == RenewalStatus.PAID

        # 4. Officer processes with regulatory authority
        renewal.mark_processing()
        assert renewal.status == RenewalStatus.PROCESSING

        # 5. Replacement document uploaded
        new_doc = Document.objects.create(
            document_type=doc_type,
            vehicle=vehicle,
            reference_number='KENHA-NEW-2027',
            issue_date=date.today(),
            expiry_date=date.today() + timedelta(days=365),
            file=SimpleUploadedFile("new.pdf", b"new official permit"),
            version=2,
            status=VerificationStatus.PENDING
        )
        renewal.upload_replacement_document(new_doc)
        assert renewal.status == RenewalStatus.DOC_UPLOADED

        # 6. Compliance verification & completion
        renewal.complete_renewal(compliance_officer)
        assert renewal.status == RenewalStatus.COMPLETED
        assert renewal.completed_at is not None

        new_doc.refresh_from_db()
        assert new_doc.status == VerificationStatus.VERIFIED
        assert new_doc.verified_by == compliance_officer

        old_doc.refresh_from_db()
        assert old_doc.status == VerificationStatus.SUPERSEDED


@pytest.mark.django_db
class TestExpenseMakerChecker:
    def test_expense_maker_checker_and_posting(self, chart_of_accounts, accounting_staff):
        period, _, _, a_bank, _, _, _, a_exp = chart_of_accounts
        treasurer, clerk, _ = accounting_staff

        # 1. Maker creates expense
        expense = Expense.objects.create(
            expense_number=Expense.generate_expense_number(),
            category=a_exp,
            payment_account=a_bank,
            amount=Decimal('6500.00'),
            date=date.today(),
            payee='Office Mart Printers',
            description='SACCO official vehicle decals and stationery',
            recorded_by=clerk,
            status='PENDING'
        )
        assert expense.status == 'PENDING'

        # 2. Checker (Treasurer) authorizes and posts to ledger
        AccountingService.post_expense(expense, user=treasurer)
        expense.refresh_from_db()

        assert expense.status == 'APPROVED'
        assert expense.approved_by == treasurer
        assert expense.journal_entry is not None
        assert expense.journal_entry.verify_balance() is True

        assert a_exp.current_balance == Decimal('6500.00')
        assert a_bank.current_balance == Decimal('-6500.00')
