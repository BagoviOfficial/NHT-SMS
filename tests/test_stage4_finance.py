import pytest
import json
from decimal import Decimal
from datetime import date, timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipCategory, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory
from nht_sacco.apps.billing.models import ServiceItem, ServicePrice, ServiceCategory, Invoice, InvoiceItem, InvoiceStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus, PaymentMethod, Receipt, ManualPaymentVoucher
from nht_sacco.apps.payments.daraja import DarajaClient
from nht_sacco.apps.accounting.models import JournalEntry, JournalLine, Account, FinancialPeriod
from nht_sacco.apps.accounting.services import AccountingService
from nht_sacco.apps.audit.models import AuditLog
from unittest.mock import patch, MagicMock
import threading

User = get_user_model()

@pytest.fixture
def finance_officer(db):
    return User.objects.create_user(
        username='treasurer_user',
        email='treasurer@nhttransporters.co.ke',
        password='TreasurerPass123!',
        role=UserRole.TREASURER
    )

@pytest.fixture
def finance_clerk(db):
    return User.objects.create_user(
        username='clerk_user',
        email='clerk@nhttransporters.co.ke',
        password='ClerkPass123!',
        role=UserRole.FIELD_OFFICER
    )

@pytest.fixture
def paying_member(db):
    user = User.objects.create_user(
        username='paying_member',
        email='payer@nhttransporters.co.ke',
        password='PayerPassword123!',
        role=UserRole.MEMBER
    )
    return Member.objects.create(
        user=user,
        membership_number='NHT-MBR-2026-4444',
        first_name='Rashid',
        last_name='Aden',
        national_id='33445566',
        phone_number='+254712345678',
        email='payer@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Fatuma Aden',
        next_of_kin_relation='Wife',
        next_of_kin_phone='+254712345679'
    )

@pytest.fixture
def other_member(db):
    user = User.objects.create_user(
        username='other_member',
        email='other@nhttransporters.co.ke',
        password='OtherPassword123!',
        role=UserRole.MEMBER
    )
    return Member.objects.create(
        user=user,
        membership_number='NHT-MBR-2026-5555',
        first_name='Osman',
        last_name='Gedi',
        national_id='33445577',
        phone_number='+254722334455',
        email='other@nhttransporters.co.ke',
        category=MembershipCategory.INDIVIDUAL_OPERATOR,
        status=MembershipStatus.ACTIVE,
        next_of_kin_name='Kin',
        next_of_kin_relation='Brother',
        next_of_kin_phone='+254722334456'
    )

@pytest.fixture
def sample_services(db):
    sub = ServiceItem.objects.create(
        code='TEST_SUB_14',
        name='14 Seater Monthly Operations',
        category=ServiceCategory.SUBSCRIPTION,
        is_statutory=False
    )
    stat = ServiceItem.objects.create(
        code='TEST_KENHA',
        name='KeNHA Highway Corridor Permit',
        category=ServiceCategory.STATUTORY,
        is_statutory=True
    )
    return sub, stat

@pytest.mark.django_db
class TestBillingAndInvoicing:
    def test_invoice_totals_and_decimal_precision(self, paying_member, sample_services):
        sub_srv, stat_srv = sample_services
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-TEST01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        # Add 2 monthly subscriptions @ 2,500.50
        InvoiceItem.objects.create(
            invoice=invoice,
            service_item=sub_srv,
            description='Monthly Ops - 2 Months',
            unit_price=Decimal('2500.50'),
            quantity=2
        )
        # Add 1 KeNHA statutory charge @ 4,500.25
        InvoiceItem.objects.create(
            invoice=invoice,
            service_item=stat_srv,
            description='KeNHA Permit',
            unit_price=Decimal('4500.25'),
            quantity=1
        )

        invoice.recalculate_totals()

        assert invoice.subtotal == Decimal('5001.00')
        assert invoice.statutory_total == Decimal('4500.25')
        assert invoice.total_amount == Decimal('9501.25')
        assert invoice.balance_due == Decimal('9501.25')
        assert invoice.status == InvoiceStatus.ISSUED

    def test_partial_payment_status_progression(self, paying_member, sample_services):
        sub_srv, _ = sample_services
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-TEST02',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14)
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            service_item=sub_srv,
            description='Monthly Fee',
            unit_price=Decimal('3000.00'),
            quantity=1
        )
        invoice.recalculate_totals()

        # Allocate partial KES 1,000.00
        invoice.allocate_payment(Decimal('1000.00'))
        assert invoice.amount_paid == Decimal('1000.00')
        assert invoice.balance_due == Decimal('2000.00')
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID

        # Settle remainder KES 2,000.00
        invoice.allocate_payment(Decimal('2000.00'))
        assert invoice.amount_paid == Decimal('3000.00')
        assert invoice.balance_due == Decimal('0.00')
        assert invoice.status == InvoiceStatus.PAID


@pytest.mark.django_db
class TestDarajaMPesaIntegration:
    def test_stk_push_initiation(self, paying_member, sample_services):
        sub_srv, _ = sample_services
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-MPESA01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('2500.00')
        )
        client = DarajaClient()
        response = client.initiate_stk_push(
            phone_number='+254712345678',
            amount=Decimal('2500.00'),
            invoice=invoice
        )
        assert response['ResponseCode'] == '0'
        checkout_id = response['CheckoutRequestID']

        # Assert local tracking payment created with status INITIATED
        payment = Payment.objects.filter(idempotency_key=checkout_id).first()
        assert payment is not None
        assert payment.status == PaymentStatus.INITIATED
        assert payment.amount == Decimal('2500.00')

    def test_stk_callback_success_and_idempotency(self, paying_member, sample_services):
        sub_srv, _ = sample_services
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-MPESA02',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('2500.00')
        )
        client = DarajaClient()
        init_res = client.initiate_stk_push(
            phone_number='+254712345678',
            amount=Decimal('2500.00'),
            invoice=invoice
        )
        checkout_id = init_res['CheckoutRequestID']

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_REQ_1001",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 2500.00},
                            {"Name": "MpesaReceiptNumber", "Value": "RKL9998887"},
                            {"Name": "TransactionDate", "Value": 20261117180000},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        # 1. First execution: Process callback
        res1 = DarajaClient.process_stk_callback(callback_payload)
        assert res1['ResultCode'] == 0

        # Assert payment confirmed & invoice settled
        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert payment.status == PaymentStatus.SUCCESS
        assert payment.provider_transaction_id == 'RKL9998887'

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('2500.00')
        assert invoice.status == InvoiceStatus.PAID
        assert hasattr(payment, 'receipt')
        assert payment.receipt.receipt_number.startswith('NHT-REC-')

        # 2. STRICT IDEMPOTENCY TEST: Re-submit identical callback
        res2 = DarajaClient.process_stk_callback(callback_payload)
        assert res2['ResultCode'] == 0
        assert 'Already processed' in res2['ResultDesc']

        # Assert invoice amount_paid is NOT doubled!
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('2500.00')

    def test_stk_callback_failure_handling(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-FAIL01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('1000.00')
        )
        client = DarajaClient()
        init_res = client.initiate_stk_push('+254712345678', Decimal('1000.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        fail_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_REQ_FAIL",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user."
                }
            }
        }

        res = DarajaClient.process_stk_callback(fail_payload)
        assert res['ResultCode'] == 0
        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert payment.status == PaymentStatus.FAILED

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.00')
        assert invoice.status == InvoiceStatus.ISSUED


@pytest.mark.django_db
class TestMakerCheckerManualPayments:
    def test_maker_checker_authorization_flow(self, client, paying_member, finance_clerk, finance_officer):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-BANK01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('15000.00')
        )

        # 1. Maker stage: Clerk records voucher
        voucher = ManualPaymentVoucher.objects.create(
            invoice=invoice,
            member=paying_member,
            method='BANK_TRANSFER',
            bank_slip_reference='KCB-DEP-778899',
            bank_name='KCB Bank Kenya',
            amount=Decimal('15000.00'),
            payment_date=date.today(),
            entered_by=finance_clerk,
            status=ManualPaymentVoucher.Status.PENDING
        )
        assert voucher.status == ManualPaymentVoucher.Status.PENDING
        assert invoice.amount_paid == Decimal('0.00')

        review_url = reverse('payments:voucher_review', kwargs={'pk': voucher.pk})

        # 2. Maker tries to approve their own voucher -> Blocked!
        client.force_login(finance_clerk)
        res_self = client.post(review_url, {'action': 'APPROVE'})
        voucher.refresh_from_db()
        assert voucher.status == ManualPaymentVoucher.Status.PENDING

        # 3. Checker stage: Independent Finance Officer reviews and approves
        client.force_login(finance_officer)
        res_approve = client.post(review_url, {'action': 'APPROVE', 'notes': 'Verified against KCB Bank statement'})
        voucher.refresh_from_db()
        assert voucher.status == ManualPaymentVoucher.Status.VERIFIED
        assert voucher.verified_by == finance_officer

        # Assert invoice settled and payment & receipt generated
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('15000.00')
        assert invoice.status == InvoiceStatus.PAID

        payment = Payment.objects.filter(provider_transaction_id='KCB-DEP-778899').first()
        assert payment is not None
        assert payment.status == PaymentStatus.SUCCESS
        assert hasattr(payment, 'receipt')

    def test_receipt_view_anti_idor(self, client, paying_member, other_member, finance_officer):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-REC01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('5000.00')
        )
        payment = Payment.objects.create(
            payment_reference='NHT-PAY-2026-9999',
            invoice=invoice,
            member=paying_member,
            method=PaymentMethod.MPESA,
            amount=Decimal('5000.00'),
            provider_transaction_id='RKL5556667',
            idempotency_key='IDEM_REC_01',
            status=PaymentStatus.SUCCESS
        )
        receipt = Receipt.objects.create(
            receipt_number='NHT-REC-2026-9999',
            payment=payment,
            issued_by=finance_officer
        )

        receipt_url = reverse('payments:receipt_detail', kwargs={'pk': receipt.pk})

        # 1. Other member (Member 2) tries to access Member 1's receipt -> 403 Forbidden
        client.force_login(other_member.user)
        res_other = client.get(receipt_url)
        assert res_other.status_code == 403

        # 2. Legitimate paying member (Member 1) accesses -> 200 OK
        client.force_login(paying_member.user)
        res_owner = client.get(receipt_url)
        assert res_owner.status_code == 200
        assert 'NHT-REC-2026-9999' in res_owner.content.decode('utf-8')
        assert 'Rashid Aden' in res_owner.content.decode('utf-8')


@pytest.mark.django_db
class TestDarajaHardenedPaymentWorkflow:
    """
    Phase II Sprint 1: Hardened Safaricom Daraja integration and financial posting tests.
    Covers OAuth authentication, transaction status verification, token authentication,
    financial parameter validation, concurrency, duplicate prevention, and balance consistency.
    """

    def test_callback_missing_and_invalid_credentials_rejected_at_view(self, client, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-SEC01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('3000.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('3000.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        callback_url = reverse('payments:mpesa_callback')
        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_SEC_01",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 3000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "SEC111222"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        # 1. Missing token -> 401 Unauthorized
        res_missing = client.post(callback_url, data=json.dumps(payload), content_type='application/json')
        assert res_missing.status_code == 401

        # 2. Invalid token in query string -> 401 Unauthorized
        res_invalid = client.post(f"{callback_url}?token=wrong-secret-token", data=json.dumps(payload), content_type='application/json')
        assert res_invalid.status_code == 401

        # 3. Valid token in query string -> 200 OK
        valid_token = daraja.callback_token
        res_valid = client.post(f"{callback_url}?token={valid_token}", data=json.dumps(payload), content_type='application/json')
        assert res_valid.status_code == 200
        assert res_valid.json().get('ResultCode') == 0

        # Assert payment confirmed & journal entry posted
        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert payment.status == PaymentStatus.SUCCESS
        assert JournalEntry.objects.filter(reference=payment.payment_reference).exists()

    def test_callback_header_token_authentication(self, client, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-SEC02',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('1200.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('1200.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        callback_url = reverse('payments:mpesa_callback')
        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_SEC_02",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 1200.00},
                            {"Name": "MpesaReceiptNumber", "Value": "SEC333444"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        # Authenticate via X-Callback-Token header
        res = client.post(
            callback_url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CALLBACK_TOKEN=daraja.callback_token
        )
        assert res.status_code == 200
        assert res.json().get('ResultCode') == 0

    def test_callback_incorrect_payment_amount_rejected(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-AMT01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('5000.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('5000.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        # Callback with fraudulent amount (1000 instead of 5000)
        bad_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_AMT_01",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 1000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "BAD_AMT_01"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        res = DarajaClient.process_stk_callback(bad_payload, token=daraja.callback_token)
        assert res['ResultCode'] == 1
        assert "Amount mismatch" in res['ResultDesc']

        # Assert invoice remains untouched
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.00')
        assert invoice.status == InvoiceStatus.ISSUED

        # Assert no receipt or journal created
        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert not hasattr(payment, 'receipt')
        assert not JournalEntry.objects.filter(reference=payment.payment_reference).exists()

    def test_callback_incorrect_phone_number_rejected(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-PH01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('2000.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('2000.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        # Callback with different phone number
        bad_phone_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_PH_01",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 2000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "BAD_PH_01"},
                            {"Name": "PhoneNumber", "Value": 254799887766}
                        ]
                    }
                }
            }
        }

        res = DarajaClient.process_stk_callback(bad_phone_payload, token=daraja.callback_token)
        assert res['ResultCode'] == 1
        assert "Phone number mismatch" in res['ResultDesc']

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.00')

    def test_callback_unknown_checkout_reference_rejected(self):
        unknown_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_UNK_01",
                    "CheckoutRequestID": "ws_CO_NONEXISTENT_TRANSACTION_9999",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 5000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "UNK_REC_01"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        daraja = DarajaClient()
        res = DarajaClient.process_stk_callback(unknown_payload, token=daraja.callback_token)
        assert res['ResultCode'] == 1
        assert "Unknown transaction reference" in res['ResultDesc']

    def test_failed_stk_request_transitions_payment_state(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-CANC01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('1500.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('1500.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        cancelled_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_CANC_01",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user."
                }
            }
        }

        res = DarajaClient.process_stk_callback(cancelled_payload, token=daraja.callback_token)
        assert res['ResultCode'] == 0
        assert "User failure" in res['ResultDesc']

        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert payment.status == PaymentStatus.FAILED

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('0.00')
        assert invoice.status == InvoiceStatus.ISSUED

    def test_duplicate_and_replayed_callbacks_are_strictly_idempotent(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-IDEM01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('4500.00')
        )
        daraja = DarajaClient()
        init_res = daraja.initiate_stk_push('+254712345678', Decimal('4500.00'), invoice)
        checkout_id = init_res['CheckoutRequestID']

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "M_IDEM_01",
                    "CheckoutRequestID": checkout_id,
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 4500.00},
                            {"Name": "MpesaReceiptNumber", "Value": "IDEM_RCP_888"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        # 1. First execution
        res1 = DarajaClient.process_stk_callback(callback_payload, token=daraja.callback_token)
        assert res1['ResultCode'] == 0

        # Assert initial confirmation
        payment = Payment.objects.get(idempotency_key=checkout_id)
        assert payment.status == PaymentStatus.SUCCESS
        receipt_count1 = Receipt.objects.filter(payment=payment).count()
        journal_count1 = JournalEntry.objects.filter(reference=payment.payment_reference).count()
        assert receipt_count1 == 1
        assert journal_count1 == 1

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('4500.00')
        assert invoice.status == InvoiceStatus.PAID

        # 2. Replay callback multiple times
        for _ in range(3):
            res_replay = DarajaClient.process_stk_callback(callback_payload, token=daraja.callback_token)
            assert res_replay['ResultCode'] == 0
            assert "Already processed" in res_replay['ResultDesc']

        # Assert no duplicate receipts, journals, or double crediting
        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('4500.00')
        assert Receipt.objects.filter(payment=payment).count() == 1
        assert JournalEntry.objects.filter(reference=payment.payment_reference).count() == 1

    def test_duplicate_journal_prevention_on_multiple_postings(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-JRN01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=7),
            total_amount=Decimal('8000.00')
        )
        payment = Payment.objects.create(
            payment_reference='NHT-PAY-2026-JRN01',
            invoice=invoice,
            member=paying_member,
            method=PaymentMethod.MPESA,
            amount=Decimal('8000.00'),
            idempotency_key='IDEM_JRN_01',
            status=PaymentStatus.INITIATED
        )

        # First settlement
        res1 = AccountingService.record_payment_settlement(
            payment=payment,
            amount=Decimal('8000.00'),
            provider_transaction_id='MPESA_JRN_01'
        )
        assert res1['status'] == 'SETTLED'
        assert JournalEntry.objects.filter(reference=payment.payment_reference).count() == 1

        # Second settlement attempt on same payment
        res2 = AccountingService.record_payment_settlement(
            payment=payment,
            amount=Decimal('8000.00'),
            provider_transaction_id='MPESA_JRN_01'
        )
        assert res2['status'] == 'ALREADY_PROCESSED'
        # Crucial: Exactly one journal entry must exist!
        assert JournalEntry.objects.filter(reference=payment.payment_reference).count() == 1

    def test_invoice_balance_consistency_across_multiple_partial_settlements(self, paying_member):
        invoice = Invoice.objects.create(
            invoice_number='NHT-INV-2026-BAL01',
            member=paying_member,
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=14),
            total_amount=Decimal('10000.00')
        )
        assert not invoice.is_fully_paid
        assert invoice.balance_due == Decimal('10000.00')

        # 1. Partial payment 1: KES 4,000
        daraja = DarajaClient()
        init1 = daraja.initiate_stk_push('+254712345678', Decimal('4000.00'), invoice)
        DarajaClient.process_stk_callback({
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": init1['CheckoutRequestID'],
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 4000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "BAL_PART_1"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }, token=daraja.callback_token)

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('4000.00')
        assert invoice.balance_due == Decimal('6000.00')
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID
        assert not invoice.is_fully_paid

        # 2. Final payment: KES 6,000
        init2 = daraja.initiate_stk_push('+254712345678', Decimal('6000.00'), invoice)
        DarajaClient.process_stk_callback({
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": init2['CheckoutRequestID'],
                    "ResultCode": 0,
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 6000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "BAL_PART_2"},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }, token=daraja.callback_token)

        invoice.refresh_from_db()
        assert invoice.amount_paid == Decimal('10000.00')
        assert invoice.balance_due == Decimal('0.00')
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.is_fully_paid

    @patch('requests.get')
    def test_genuine_daraja_oauth_flow_mocked(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "mock_daraja_access_token_9999",
            "expires_in": "3599"
        }
        mock_get.return_value = mock_response

        client = DarajaClient()
        token = client.get_oauth_token(force_refresh=True)
        assert token == "mock_daraja_access_token_9999"
        mock_get.assert_called_once()

        # Second call should use cache
        cached_token = client.get_oauth_token()
        assert cached_token == "mock_daraja_access_token_9999"
        assert mock_get.call_count == 1

    @patch('requests.post')
    def test_transaction_status_query_mocked(self, mock_post):
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {
            "ResponseCode": "0",
            "ResponseDescription": "The service request has been accepted successfully",
            "MerchantRequestID": "M_QUERY_01",
            "CheckoutRequestID": "ws_CO_QUERY_01",
            "ResultCode": "0",
            "ResultDesc": "The service request is processed successfully."
        }
        mock_post.return_value = mock_post_response

        with patch.object(DarajaClient, 'get_oauth_token', return_value='mock_oauth_token'):
            client = DarajaClient()
            res = client.query_transaction_status('ws_CO_QUERY_01')
            assert res['ResultCode'] == '0'
            assert res['CheckoutRequestID'] == 'ws_CO_QUERY_01'

