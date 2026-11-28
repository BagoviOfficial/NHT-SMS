"""
Shared payment workflows: M-Pesa STK Push initiation and Maker-Checker voucher review.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from nht_sacco.apps.accounting.services import AccountingService
from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from .daraja import DarajaClient
from .models import ManualPaymentVoucher, Payment, PaymentMethod, PaymentStatus


class PaymentWorkflowService:
    @staticmethod
    def initiate_invoice_stk(*, invoice, phone_number):
        """
        Initiates Safaricom Daraja STK Push for an unpaid invoice.
        Returns `(ok: bool, data_or_error_msg)`.
        """
        phone = (phone_number or '').strip()
        if not phone:
            raise ValidationError("Phone number is required for M-Pesa STK Push.")
        if invoice.is_fully_paid:
            raise ValidationError("Invoice is already settled in full.")

        res = DarajaClient().initiate_stk_push(
            phone_number=phone,
            amount=invoice.balance_due,
            invoice=invoice,
            account_reference=invoice.invoice_number,
            transaction_desc=f"NHT {invoice.invoice_number[-8:]}",
        )
        if str(res.get('ResponseCode')) == '0':
            return True, res
        err_msg = res.get('CustomerMessage') or res.get('ResponseDescription') or 'STK Push failed.'
        return False, err_msg

    @staticmethod
    @transaction.atomic
    def review_voucher(*, voucher, verifier, action, notes='', channel='SPA'):
        """
        Executes Maker-Checker approval or rejection of a ManualPaymentVoucher.
        """
        if voucher.entered_by_id == verifier.id:
            raise PermissionDenied("Maker-Checker Violation: You cannot review a payment voucher you entered.")
        if voucher.status != ManualPaymentVoucher.Status.PENDING:
            raise ValidationError(f"Voucher is already {voucher.status}.")

        if action == 'APPROVE':
            voucher.status = ManualPaymentVoucher.Status.VERIFIED
            voucher.verified_by = verifier
            voucher.verified_at = timezone.now()
            voucher.verification_notes = notes
            voucher.save()

            payment = Payment.objects.create(
                payment_reference=Payment.generate_payment_reference(),
                invoice=voucher.invoice,
                member=voucher.member,
                method=PaymentMethod.BANK_TRANSFER if voucher.method == 'BANK_TRANSFER' else PaymentMethod.CASH,
                amount=voucher.amount,
                idempotency_key=f"MANUAL_{voucher.id}",
                status=PaymentStatus.INITIATED,
                phone_number=voucher.member.phone_number,
                confirmed_at=timezone.now(),
            )
            settlement = AccountingService.record_payment_settlement(
                payment=payment,
                amount=voucher.amount,
                provider_transaction_id=voucher.bank_slip_reference,
                user=verifier,
                notes=f"Manual payment voucher verified via {channel} by {verifier.username} ({voucher.bank_slip_reference})",
            )
            receipt = settlement.get('receipt')
            AuditLog.objects.create(
                actor=verifier,
                action=AuditAction.APPROVE,
                entity_type='ManualPaymentVoucher',
                entity_id=str(voucher.pk),
                outcome=AuditOutcome.SUCCESS,
                change_details={
                    'slip_reference': voucher.bank_slip_reference,
                    'amount': str(voucher.amount),
                    'receipt_no': receipt.receipt_number if receipt else None,
                    'journal_no': settlement['journal_entry'].entry_number if settlement.get('journal_entry') else None,
                },
            )
            return {'voucher': voucher, 'receipt': receipt, 'settlement': settlement}

        if action == 'REJECT':
            voucher.status = ManualPaymentVoucher.Status.REJECTED
            voucher.verified_by = verifier
            voucher.verified_at = timezone.now()
            voucher.verification_notes = notes
            voucher.save()
            return {'voucher': voucher, 'receipt': None, 'settlement': None}

        raise ValidationError(f"Unsupported voucher action '{action}'.")
