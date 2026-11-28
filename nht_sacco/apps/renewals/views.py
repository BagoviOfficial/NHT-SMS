from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from .models import RenewalRequest
from .services import RenewalService


class RenewalRequestReviewView(LoginRequiredMixin, View):
    """
    Renewal Officer review endpoint: reviews member application and generates fee invoice.
    """
    def post(self, request, pk, *args, **kwargs):
        renewal = get_object_or_404(RenewalRequest, pk=pk)
        user = request.user

        if not (user.is_superuser or user.is_renewal_staff or user.is_chairman):
            return HttpResponseForbidden("Access Denied: Only SACCO Renewal Officers can process renewal workflows.")

        action = request.POST.get('action')
        notes = request.POST.get('notes', '')
        fee = Decimal(request.POST.get('fee', '1000.00'))

        _, invoice = RenewalService.review_and_invoice(
            renewal=renewal,
            officer=user,
            action=action,
            fee=fee,
            notes=notes,
        )
        if action == 'APPROVE_INVOICE' and invoice:
            messages.success(request, f"Renewal {renewal.request_number} approved. Invoice {invoice.invoice_number} generated.")
        elif action == 'REJECT':
            messages.warning(request, f"Renewal {renewal.request_number} rejected.")

        return redirect('/admin/#renewals')
