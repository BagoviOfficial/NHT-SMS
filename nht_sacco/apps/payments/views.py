import json
from decimal import Decimal
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
from .models import Payment, Receipt, ManualPaymentVoucher, PaymentStatus, PaymentMethod
from .daraja import DarajaClient
from nht_sacco.apps.billing.models import Invoice
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

@method_decorator(csrf_exempt, name='dispatch')
class MPesaCallbackView(View):
    """
    Webhook endpoint for Safaricom Daraja STK Push callbacks.
    URL: /api/v1/payments/mpesa/callback/
    """
    def post(self, request, *args, **kwargs):
        token = request.GET.get('token')
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON body'}, status=400)

        result = DarajaClient.process_stk_callback(payload, token=token)
        return JsonResponse(result, status=200)


class ManualPaymentVoucherReviewView(LoginRequiredMixin, View):
    """
    Maker-Checker Authorization Controller for Manual Bank Deposits & Cash Payments.
    Enforces separation of duties: Creator cannot approve their own voucher.
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

            # Record cleared Payment
            payment = Payment.objects.create(
                payment_reference=Payment.generate_payment_reference(),
                invoice=voucher.invoice,
                member=voucher.member,
                method=PaymentMethod.BANK_TRANSFER if voucher.method == 'BANK_TRANSFER' else PaymentMethod.CASH,
                amount=voucher.amount,
                provider_transaction_id=voucher.bank_slip_reference,
                idempotency_key=f"MANUAL_{voucher.id}",
                status=PaymentStatus.SUCCESS,
                confirmed_at=timezone.now()
            )

            # Settle invoice balance
            voucher.invoice.allocate_payment(voucher.amount)

            # Generate Receipt
            receipt = Receipt.objects.create(
                receipt_number=Receipt.generate_receipt_number(),
                payment=payment,
                issued_by=request.user
            )

            AuditLog.objects.create(
                actor=request.user,
                action=AuditAction.APPROVE,
                entity_type='ManualPaymentVoucher',
                entity_id=str(voucher.pk),
                outcome=AuditOutcome.SUCCESS,
                change_details={
                    'slip_reference': voucher.bank_slip_reference,
                    'amount': str(voucher.amount),
                    'receipt_no': receipt.receipt_number
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
