import json
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.integrations.branding import DocumentBrandingService
from nht_sacco.config.mui import render_mui_app
from .daraja import DarajaClient
from .models import ManualPaymentVoucher, Receipt
from .services import PaymentWorkflowService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class MPesaCallbackView(View):
    """
    Webhook endpoint for Safaricom Daraja STK Push callbacks.
    URL: /api/v1/payments/mpesa/callback/
    """
    def post(self, request, *args, **kwargs):
        token = request.GET.get('token')
        if not token:
            token = request.headers.get('x-callback-token')
        if not token:
            auth_header = request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]

        expected_token = getattr(settings, 'MPESA_CALLBACK_TOKEN', os.getenv('MPESA_CALLBACK_TOKEN', 'nht-mpesa-token-secret'))

        if not token or token != expected_token:
            logger.warning("[Daraja Security] Unauthorized callback attempt from IP %s", request.META.get('REMOTE_ADDR'))
            AuditLog.objects.create(
                actor=None,
                actor_username='ANONYMOUS_GATEWAY',
                action=AuditAction.VIEW,
                entity_type='MPesaCallback',
                entity_id='UNAUTHORIZED',
                outcome=AuditOutcome.DENIED,
                change_details={'error': 'Unauthorized callback: missing or invalid authentication token'},
            )
            return JsonResponse(
                {'ResultCode': 1, 'ResultDesc': 'Unauthorized: Missing or invalid callback token'},
                status=401,
            )

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON body'}, status=400)

        result = DarajaClient.process_stk_callback(payload, token=token)
        return JsonResponse(result, status=200)


class ManualPaymentVoucherReviewView(LoginRequiredMixin, View):
    """
    Maker-Checker Authorization Controller for Manual Bank Deposits & Cash Payments.
    """
    def post(self, request, pk, *args, **kwargs):
        voucher = get_object_or_404(ManualPaymentVoucher, pk=pk)

        if not (request.user.is_superuser or request.user.is_financial_staff):
            return HttpResponseForbidden("Access Denied: Only SACCO Finance Personnel can verify payment vouchers.")

        action = request.POST.get('action')
        notes = request.POST.get('notes', '')

        try:
            result = PaymentWorkflowService.review_voucher(
                voucher=voucher,
                verifier=request.user,
                action=action,
                notes=notes,
                channel='WEB',
            )
            if action == 'APPROVE' and result.get('receipt'):
                messages.success(
                    request,
                    f"Voucher {voucher.bank_slip_reference} verified. Receipt {result['receipt'].receipt_number} issued.",
                )
            elif action == 'REJECT':
                messages.warning(request, f"Voucher {voucher.bank_slip_reference} has been rejected.")
        except PermissionDenied:
            messages.error(request, "Maker-Checker Violation: You cannot approve a payment voucher you entered.")
        except ValidationError as exc:
            messages.warning(request, str(exc))

        return redirect('/admin/#payments')


class ReceiptDetailView(LoginRequiredMixin, View):
    """
    Renders an official, printable SACCO payment receipt inside the unified MUI shell.
    """
    def get(self, request, pk, *args, **kwargs):
        receipt = get_object_or_404(
            Receipt.objects.select_related('payment', 'payment__member', 'payment__invoice', 'branding_version'),
            pk=pk,
        )
        user = request.user
        if user.is_member and receipt.payment.member.user != user:
            raise PermissionDenied("Access Denied: You cannot view another member's receipt.")

        brand = DocumentBrandingService.get_branding_context(branding_version=receipt.branding_version)
        if brand.get('has_logo') and receipt.branding_version_id:
            receipt_logo_url = f"/settings/api/v1/company-profile/logo-asset/?version={receipt.branding_version.version_number}"
        elif brand.get('has_logo'):
            receipt_logo_url = "/settings/api/v1/company-profile/logo-asset/"
        else:
            receipt_logo_url = ''

        pay = receipt.payment
        return render_mui_app(
            request,
            initial_route='receipt-detail',
            page_title=f"Official Payment Receipt - {receipt.receipt_number}",
            page_data={
                'receipt': {
                    'id': str(receipt.pk),
                    'receipt_number': receipt.receipt_number,
                    'issued_at': receipt.issued_at.isoformat() if receipt.issued_at else '',
                    'member_name': pay.member.full_name,
                    'membership_number': pay.member.membership_number,
                    'phone_number': pay.member.phone_number,
                    'method': pay.get_method_display(),
                    'reference': pay.provider_transaction_id or pay.payment_reference,
                    'payment_reference': pay.payment_reference,
                    'invoice_number': pay.invoice.invoice_number,
                    'amount': str(pay.amount),
                    'balance_due': str(pay.invoice.balance_due),
                    'pdf_url': f"/api/v1/receipts/{receipt.pk}/download_pdf/",
                    'brand': {
                        'trading_name': brand.get('trading_name', ''),
                        'legal_name': brand.get('legal_name', ''),
                        'version_number': brand.get('version_number', 1),
                        'logo_url': receipt_logo_url,
                    },
                }
            },
        )
