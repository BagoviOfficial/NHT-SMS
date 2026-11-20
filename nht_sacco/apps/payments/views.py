import json
import logging
from decimal import Decimal
from django.conf import settings
from django.views import View
from django.views.generic import DetailView
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
import os

from .models import Payment, Receipt, ManualPaymentVoucher, PaymentStatus, PaymentMethod
from .daraja import DarajaClient
from nht_sacco.apps.billing.models import Invoice
from nht_sacco.apps.accounting.services import AccountingService
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MPesaCallbackView(View):
    """
    Webhook endpoint for Safaricom Daraja STK Push callbacks.
    URL: /api/v1/payments/mpesa/callback/

    Security Hardening:
    - Enforces token authentication via query parameter (?token=...) or HTTP header (X-Callback-Token / Authorization: Bearer).
    - Rejects unauthenticated requests with HTTP 401 and security audit logging.
    - Validates JSON payload integrity.
    """
    def post(self, request, *args, **kwargs):
        # 1. Extract callback token
        token = request.GET.get('token')
        if not token:
            token = request.headers.get('x-callback-token')
        if not token:
            auth_header = request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]

        expected_token = getattr(settings, 'MPESA_CALLBACK_TOKEN', os.getenv('MPESA_CALLBACK_TOKEN', 'nht-mpesa-token-secret'))

        # 2. Authenticate callback origin
        if not token or token != expected_token:
            logger.warning("[Daraja Security] Unauthorized callback attempt from IP %s", request.META.get('REMOTE_ADDR'))
            AuditLog.objects.create(
                actor=None,
                actor_username='ANONYMOUS_GATEWAY',
                action=AuditAction.VIEW,
                entity_type='MPesaCallback',
                entity_id='UNAUTHORIZED',
                outcome=AuditOutcome.DENIED,
                change_details={'error': 'Unauthorized callback: missing or invalid authentication token'}
            )
            return JsonResponse(
                {'ResultCode': 1, 'ResultDesc': 'Unauthorized: Missing or invalid callback token'},
                status=401
            )

        # 3. Parse JSON Body
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON body'}, status=400)

        # 4. Safely process callback with full financial validation
        result = DarajaClient.process_stk_callback(payload, token=token)
        return JsonResponse(result, status=200)


class ManualPaymentVoucherReviewView(LoginRequiredMixin, View):
    """
    Maker-Checker Authorization Controller for Manual Bank Deposits & Cash Payments.
    Enforces separation of duties: Creator cannot approve their own voucher.
    Transactions are posted through the centralized AccountingService to guarantee
    double-entry GL compliance, receipt generation, and audit logging.
    """
    def post(self, request, pk, *args, **kwargs):
        voucher = get_object_or_404(ManualPaymentVoucher, pk=pk)

        # Check permission: only financial staff can review
        if not (request.user.is_superuser or request.user.is_financial_staff):
            return HttpResponseForbidden("Access Denied: Only SACCO Finance Personnel can verify payment vouchers.")

        # STRICT MAKER-CHECKER RULE
        if voucher.entered_by == request.user and not request.user.is_superuser:
            messages.error(request, "Maker-Checker Violation: You cannot approve a payment voucher you entered.")
            return redirect('/admin/payments/manualpaymentvoucher/')

        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        if action == 'APPROVE':
            voucher.status = ManualPaymentVoucher.Status.VERIFIED
            voucher.verified_by = request.user
            voucher.verified_at = timezone.now()
            voucher.verification_notes = notes
            voucher.save()

            # Record initiated Payment record
            payment = Payment.objects.create(
                payment_reference=Payment.generate_payment_reference(),
                invoice=voucher.invoice,
                member=voucher.member,
                method=PaymentMethod.BANK_TRANSFER if voucher.method == 'BANK_TRANSFER' else PaymentMethod.CASH,
                amount=voucher.amount,
                idempotency_key=f"MANUAL_{voucher.id}",
                status=PaymentStatus.INITIATED,
                phone_number=voucher.member.phone_number,
                confirmed_at=timezone.now()
            )

            # Centralised settlement: confirms payment, allocates invoice, issues receipt, and posts double-entry GL journal
            settlement = AccountingService.record_payment_settlement(
                payment=payment,
                amount=voucher.amount,
                provider_transaction_id=voucher.bank_slip_reference,
                user=request.user,
                notes=f"Manual payment voucher verified by {request.user.username} ({voucher.bank_slip_reference})"
            )
            receipt = settlement['receipt']

            AuditLog.objects.create(
                actor=request.user,
                action=AuditAction.APPROVE,
                entity_type='ManualPaymentVoucher',
                entity_id=str(voucher.pk),
                outcome=AuditOutcome.SUCCESS,
                change_details={
                    'slip_reference': voucher.bank_slip_reference,
                    'amount': str(voucher.amount),
                    'receipt_no': receipt.receipt_number if receipt else None,
                    'journal_no': settlement['journal_entry'].entry_number if settlement.get('journal_entry') else None
                }
            )
            messages.success(request, f"Voucher {voucher.bank_slip_reference} verified. Receipt {receipt.receipt_number} issued.")

        elif action == 'REJECT':
            voucher.status = ManualPaymentVoucher.Status.REJECTED
            voucher.verified_by = request.user
            voucher.verified_at = timezone.now()
            voucher.verification_notes = notes
            voucher.save()
            messages.warning(request, f"Voucher {voucher.bank_slip_reference} has been rejected.")

        return redirect('/admin/payments/manualpaymentvoucher/')


class ReceiptDetailView(LoginRequiredMixin, DetailView):
    """
    Renders an official, printable SACCO payment receipt.
    """
    model = Receipt
    template_name = 'finance/receipt.html'
    context_object_name = 'receipt'

    def get_object(self, queryset=None):
        receipt = super().get_object(queryset)
        user = self.request.user
        # Strict object isolation: Member can only view their own receipts
        if user.is_member and receipt.payment.member.user != user:
            raise PermissionDenied("Access Denied: You cannot view another member's receipt.")
        return receipt
