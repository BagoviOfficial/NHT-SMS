from decimal import Decimal
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.utils import timezone
from .models import RenewalRequest, RenewalStatus
from nht_sacco.apps.documents.models import Document, VerificationStatus
from nht_sacco.apps.billing.models import Invoice, InvoiceItem, ServiceItem
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

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

        if action == 'APPROVE_INVOICE':
            # Create automated Invoice
            today = timezone.localdate()
            invoice = Invoice.objects.create(
                invoice_number=Invoice.generate_invoice_number(),
                member=renewal.member,
                vehicle=renewal.vehicle,
                issue_date=today,
                due_date=today + timezone.timedelta(days=7),
                notes=f"Renewal fee for {renewal.document_type.name} on {renewal.vehicle.registration_number}"
            )
            # Find renewal fee service
            service = ServiceItem.objects.filter(category='RENEWAL').first()
            fee = Decimal(request.POST.get('fee', '1000.00'))
            if service:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    service_item=service,
                    description=f"{renewal.document_type.name} Renewal Fee",
                    unit_price=fee,
                    quantity=1
                )
                invoice.recalculate_totals()

            renewal.mark_reviewed(officer_user=user, invoice=invoice)
            messages.success(request, f"Renewal {renewal.request_number} approved. Invoice {invoice.invoice_number} generated.")

        elif action == 'REJECT':
            renewal.status = RenewalStatus.REJECTED
            renewal.notes = notes
            renewal.save()
            messages.warning(request, f"Renewal {renewal.request_number} rejected.")

        return redirect('/admin/renewals/renewalrequest/')
