"""
Shared document renewal workflow service.
"""

from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.billing.models import Invoice, InvoiceItem, ServiceItem
from nht_sacco.apps.documents.models import Document
from .models import RenewalRequest, RenewalStatus


class RenewalService:
    @staticmethod
    def submit_renewal(*, member, vehicle, document_type, actor, notes=''):
        """
        Creates a new RenewalRequest linked to the latest document of that type.
        """
        current_doc = (
            Document.objects.filter(vehicle=vehicle, document_type=document_type)
            .order_by('-expiry_date')
            .first()
        )
        req = RenewalRequest.objects.create(
            request_number=RenewalRequest.generate_request_number(),
            member=member,
            vehicle=vehicle,
            document_type=document_type,
            current_document=current_doc,
            status=RenewalStatus.SUBMITTED,
            notes=notes,
        )
        AuditLog.log_action(
            actor=actor,
            action=AuditAction.CREATE,
            entity_type='RenewalRequest',
            entity_id=req.request_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Submitted renewal {req.request_number} for {vehicle.registration_number} ({document_type.name})",
        )
        return req

    @staticmethod
    @transaction.atomic
    def review_and_invoice(*, renewal, officer, action='APPROVE_INVOICE', fee=Decimal('1000.00'), notes=''):
        """
        Processes Renewal Officer review: either issues a renewal fee invoice
        or rejects the renewal request.
        """
        if action == 'REJECT':
            renewal.status = RenewalStatus.REJECTED
            renewal.notes = notes or renewal.notes
            renewal.save()
            return renewal, None

        today = timezone.localdate()
        invoice = Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            member=renewal.member,
            vehicle=renewal.vehicle,
            issue_date=today,
            due_date=today + timezone.timedelta(days=7),
            notes=f"Renewal fee for {renewal.document_type.name} on {renewal.vehicle.registration_number}",
            created_by=officer,
        )
        service = (
            ServiceItem.objects.filter(category='RENEWAL', is_active=True).first()
            or ServiceItem.objects.filter(is_active=True).first()
        )
        if service:
            InvoiceItem.objects.create(
                invoice=invoice,
                service_item=service,
                description=f"{renewal.document_type.name} Renewal Fee",
                unit_price=fee,
                quantity=1,
            )
            invoice.recalculate_totals()

        renewal.mark_reviewed(officer_user=officer, invoice=invoice)
        return renewal, invoice
