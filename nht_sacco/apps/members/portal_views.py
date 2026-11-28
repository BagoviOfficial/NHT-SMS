import logging
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.billing.models import Invoice
from nht_sacco.apps.billing.services import BillingStatementService
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.documents.models import Document, DocumentType
from nht_sacco.apps.incidents.models import Incident, IncidentSeverity, IncidentStatus, IncidentType
from nht_sacco.apps.members.models import MembershipStatus
from nht_sacco.apps.notifications.models import (
    Announcement,
    CommunicationPreference,
    Notification,
)
from nht_sacco.apps.payments.models import PaymentStatus, Receipt
from nht_sacco.apps.payments.services import PaymentWorkflowService
from nht_sacco.apps.renewals.models import RenewalRequest
from nht_sacco.apps.renewals.services import RenewalService
from nht_sacco.apps.vehicles.models import (
    COMMERCIAL_VEHICLE_CATEGORIES,
    ComplianceCardStatus,
    FuelType,
    Vehicle,
    VehicleCategory,
    VehicleComplianceCard,
    VehicleStatus,
)
from nht_sacco.apps.vehicles.qr import generate_qr_base64
from nht_sacco.apps.vehicles.services import ComplianceCardService
from nht_sacco.config.mui import render_mui_app

logger = logging.getLogger(__name__)


def member_required(view_func):
    """
    Decorator requiring authenticated user with an associated active Member profile.
    Strictly forbids staff or unlinked accounts from member self-service portal.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'member_profile') or request.user.member_profile is None:
            AuditLog.log_action(
                actor=request.user,
                action=AuditAction.VIEW,
                entity_type='MemberPortal',
                outcome=AuditOutcome.DENIED,
                notes=f"Non-member user {request.user.username} (role: {request.user.role}) denied access to member portal.",
            )
            raise PermissionDenied("Access Denied: Only registered SACCO members can access the Member Portal.")

        member = request.user.member_profile
        if member.status == MembershipStatus.TERMINATED:
            raise PermissionDenied("Access Denied: Your membership has been terminated. Contact SACCO Secretariat.")

        request.member = member
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _get_owned_vehicle_or_403(request, vehicle_id, entity_type='Vehicle'):
    vehicle = Vehicle.objects.filter(id=vehicle_id).first()
    if not vehicle:
        raise Http404("Vehicle not found")
    if vehicle.current_owner != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.VIEW,
            entity_type=entity_type,
            entity_id=vehicle.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR Security Violation: User {request.user.username} attempted to access {entity_type} for {vehicle.registration_number}.",
        )
        raise PermissionDenied("Access Denied: You do not own this vehicle.")
    return vehicle


def _get_owned_invoice_or_403(request, invoice_id, action=AuditAction.VIEW):
    invoice = Invoice.objects.filter(id=invoice_id).select_related('member', 'vehicle').first()
    if not invoice:
        raise Http404("Invoice not found")
    if invoice.member != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=action,
            entity_type='Invoice',
            entity_id=invoice.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR violation: Member attempted to access invoice {invoice.invoice_number} of another member.",
        )
        raise PermissionDenied("Access Denied: You do not own this invoice.")
    return invoice


def _render_portal_mui(request, *, section='dashboard', title='Member Portal', portal_data=None):
    data = {
        'section': section,
        'member_name': request.member.full_name,
        'membership_number': request.member.membership_number,
    }
    if portal_data:
        data.update(portal_data)
    return render_mui_app(
        request,
        initial_route='member-portal',
        page_title=title,
        page_data={'portal': data},
    )


@member_required
def portal_dashboard(request):
    member = request.member
    vehicles = member.vehicles.all()
    compliant_count = expiring_soon_count = non_compliant_count = 0
    for v in vehicles:
        st = ComplianceService.check_vehicle_compliance(v)['status']
        if st == 'FULLY_COMPLIANT':
            compliant_count += 1
        elif st == 'EXPIRING_SOON':
            expiring_soon_count += 1
        else:
            non_compliant_count += 1

    invoices = member.invoices.all()
    total_invoiced = invoices.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_paid = invoices.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    return _render_portal_mui(
        request,
        section='dashboard',
        title='Member Portal Dashboard',
        portal_data={
            'total_vehicles': vehicles.count(),
            'compliant_count': compliant_count,
            'expiring_soon_count': expiring_soon_count,
            'non_compliant_count': non_compliant_count,
            'total_invoiced': str(total_invoiced),
            'total_paid': str(total_paid),
            'balance_due': str(total_invoiced - total_paid),
            'announcements': list(Announcement.objects.filter(is_published=True).order_by('-created_at').values('title', 'content')[:3]),
        },
    )


@member_required
def portal_vehicles(request):
    vehicles_data = [
        {
            'id': str(v.id),
            'registration_number': v.registration_number,
            'make_model': f"{v.make} {v.model}",
            'compliance': ComplianceService.check_vehicle_compliance(v)['status'],
        }
        for v in request.member.vehicles.all().order_by('registration_number')
    ]
    return _render_portal_mui(request, section='vehicles', title='My Fleet', portal_data={'vehicles': vehicles_data})


@member_required
def portal_vehicle_detail(request, vehicle_id):
    vehicle = _get_owned_vehicle_or_403(request, vehicle_id, entity_type='Vehicle')
    comp = ComplianceService.check_vehicle_compliance(vehicle)
    docs = [
        {
            'id': str(d.id),
            'type': d.document_type.name,
            'reference_number': d.reference_number,
            'expiry_date': str(d.expiry_date) if d.expiry_date else '',
            'status': d.status,
        }
        for d in Document.objects.filter(vehicle=vehicle).select_related('document_type').order_by('-issue_date')
    ]
    return _render_portal_mui(
        request,
        section='vehicle-detail',
        title=f"Vehicle {vehicle.registration_number}",
        portal_data={
            'vehicle': {
                'id': str(vehicle.id),
                'registration_number': vehicle.registration_number,
                'make': vehicle.make,
                'model': vehicle.model,
                'compliance': comp['status'],
            },
            'documents': docs,
        },
    )


@member_required
def portal_vehicle_card(request, vehicle_id):
    vehicle = _get_owned_vehicle_or_403(request, vehicle_id, entity_type='VehicleCard')
    comp = ComplianceService.check_vehicle_compliance(vehicle)
    active_card = VehicleComplianceCard.objects.filter(
        vehicle=vehicle,
        status=ComplianceCardStatus.VALID,
    ).order_by('-created_at').first()
    if active_card:
        verify_url = ComplianceCardService.get_verify_url(active_card, request=request)
    else:
        verify_url = request.build_absolute_uri(f"/verify/vehicle/{vehicle.qr_token}/")
    qr_data_uri = generate_qr_base64(verify_url) if verify_url else ''
    return _render_portal_mui(
        request,
        section='vehicle-card',
        title=f"Compliance Card - {vehicle.registration_number}",
        portal_data={
            'vehicle_card': {
                'registration_number': vehicle.registration_number,
                'compliance': comp['status'],
                'certificate_number': active_card.certificate_number if active_card else '',
                'verify_url': verify_url,
                'qr_data_uri': qr_data_uri,
            }
        },
    )


@member_required
def portal_vehicle_register(request):
    if request.method == 'POST':
        reg_num = request.POST.get('registration_number', '').strip().upper()
        chassis = request.POST.get('chassis_number', '').strip().upper()
        engine = request.POST.get('engine_number', '').strip().upper()
        make = request.POST.get('make', '').strip()
        model_name = request.POST.get('model', '').strip()
        year = request.POST.get('year_of_manufacture', '').strip()
        category = request.POST.get('category', VehicleCategory.HEAVY_TRUCK)
        fuel_type = request.POST.get('fuel_type', FuelType.NONE if category == VehicleCategory.SEMI_TRAILER else FuelType.DIESEL)
        capacity = request.POST.get('carrying_capacity', '15')

        is_trailer = category == VehicleCategory.SEMI_TRAILER or fuel_type == FuelType.NONE
        if not reg_num or not chassis or (not engine and not is_trailer) or not make or not model_name:
            messages.error(request, "All required vehicle fields must be provided.")
            return redirect('portal:vehicle_register')

        if Vehicle.objects.filter(registration_number=reg_num).exists():
            messages.error(request, f"Vehicle plate {reg_num} is already registered in the system.")
            return redirect('portal:vehicle_register')

        try:
            v = Vehicle.objects.create(
                registration_number=reg_num,
                chassis_number=chassis,
                engine_number=engine or None,
                make=make,
                model=model_name,
                year_of_manufacture=int(year) if year.isdigit() else timezone.now().year,
                category=category,
                fuel_type=fuel_type,
                carrying_capacity=int(capacity) if capacity.isdigit() else 15,
                current_owner=request.member,
                status=VehicleStatus.PENDING,
                created_by=request.user,
            )
            AuditLog.log_action(
                actor=request.user,
                action=AuditAction.CREATE,
                entity_type='Vehicle',
                entity_id=v.id,
                outcome=AuditOutcome.SUCCESS,
                notes=f"Member submitted new commercial vehicle {reg_num} for onboarding.",
            )
            messages.success(request, f"Vehicle {reg_num} submitted successfully. It is currently pending Secretariat verification.")
            return redirect('portal:vehicles')
        except Exception as exc:
            messages.error(request, f"Failed to register vehicle: {exc}")
            return redirect('portal:vehicle_register')

    return _render_portal_mui(
        request,
        section='vehicle-register',
        title='Register Vehicle',
        portal_data={
            'categories': [{'value': c.value, 'label': str(c.label)} for c in COMMERCIAL_VEHICLE_CATEGORIES],
            'fuel_types': [{'value': f.value, 'label': str(f.label)} for f in FuelType],
        },
    )


@member_required
def portal_invoices(request):
    invoices = [
        {
            'id': str(inv.id),
            'invoice_number': inv.invoice_number,
            'total_amount': str(inv.total_amount),
            'balance_due': str(inv.balance_due),
            'status': inv.status,
        }
        for inv in request.member.invoices.all().select_related('vehicle').order_by('-issue_date')
    ]
    return _render_portal_mui(request, section='invoices', title='My Invoices', portal_data={'invoices': invoices})


@member_required
def portal_invoice_detail(request, invoice_id):
    invoice = _get_owned_invoice_or_403(request, invoice_id, action=AuditAction.VIEW)
    items = [
        {
            'service_name': it.service_item.name,
            'description': it.description,
            'quantity': it.quantity,
            'unit_price': str(it.unit_price),
            'line_total': str(it.total_price),
        }
        for it in invoice.line_items.select_related('service_item').all()
    ]
    payments = [
        {
            'reference': p.provider_transaction_id or p.payment_reference,
            'amount': str(p.amount),
            'status': p.status,
        }
        for p in invoice.payments.filter(status=PaymentStatus.SUCCESS).order_by('-created_at')
    ]
    return _render_portal_mui(
        request,
        section='invoice-detail',
        title=f"Invoice {invoice.invoice_number}",
        portal_data={
            'invoice': {
                'id': str(invoice.id),
                'invoice_number': invoice.invoice_number,
                'total_amount': str(invoice.total_amount),
                'balance_due': str(invoice.balance_due),
                'status': invoice.status,
                'items': items,
                'payments': payments,
            }
        },
    )


@member_required
def portal_invoice_pay_stk(request, invoice_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        invoice = _get_owned_invoice_or_403(request, invoice_id, action=AuditAction.UPDATE)
    except Http404:
        return JsonResponse({'error': 'Invoice not found'}, status=404)

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'
    phone = request.POST.get('phone_number') or request.member.phone_number

    try:
        ok, res = PaymentWorkflowService.initiate_invoice_stk(invoice=invoice, phone_number=phone)
        if ok:
            if is_ajax:
                return JsonResponse({'success': True, 'data': res}, status=200)
            messages.success(request, f"M-Pesa STK Push prompted to {phone}. Enter your PIN to complete settlement.")
        else:
            if is_ajax:
                return JsonResponse({'error': f"M-Pesa Error: {res}"}, status=400)
            messages.error(request, f"M-Pesa Error: {res}")
    except ValidationError as exc:
        msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
        if is_ajax:
            return JsonResponse({'error': msg}, status=400)
        messages.info(request, msg)
    except Exception as exc:
        logger.exception("STK push error on invoice %s", invoice.invoice_number)
        if is_ajax:
            return JsonResponse({'error': f"STK Push error: {exc}"}, status=500)
        messages.error(request, f"STK Push error: {exc}")

    return redirect('portal:invoice_detail', invoice_id=invoice.id)


@member_required
def portal_receipts(request):
    receipts = [
        {
            'id': str(r.id),
            'receipt_number': r.receipt_number,
            'invoice_number': r.payment.invoice.invoice_number,
            'amount': str(r.payment.amount),
            'issued_at': r.issued_at.isoformat() if r.issued_at else '',
        }
        for r in Receipt.objects.filter(payment__invoice__member=request.member)
        .select_related('payment', 'payment__invoice')
        .order_by('-issued_at')
    ]
    return _render_portal_mui(request, section='receipts', title='My Receipts', portal_data={'receipts': receipts})


@member_required
def portal_statement(request):
    statement = BillingStatementService.build_member_statement(request.member)
    return _render_portal_mui(
        request,
        section='statement',
        title='Financial Statement',
        portal_data={
            'statement': {
                'member_name': statement['member_name'],
                'membership_number': statement['membership_number'],
                'total_debits': str(statement['total_debits']),
                'total_credits': str(statement['total_credits']),
                'current_balance': str(statement['current_balance']),
                'entries': [
                    {
                        'date': e['date_iso'],
                        'type': e['type'],
                        'reference': e['reference'],
                        'description': e['description'],
                        'debit': str(e['debit']),
                        'credit': str(e['credit']),
                        'running_balance': str(e['running_balance']),
                    }
                    for e in statement['entries']
                ],
            }
        },
    )


@member_required
def portal_renewals(request):
    renewals = [
        {
            'id': str(r.id),
            'request_number': r.request_number,
            'vehicle': r.vehicle.registration_number,
            'document_type': r.document_type.name,
            'status': r.status,
        }
        for r in RenewalRequest.objects.filter(member=request.member)
        .select_related('vehicle', 'document_type', 'invoice')
        .order_by('-created_at')
    ]
    return _render_portal_mui(request, section='renewals', title='Document Renewals', portal_data={'renewals': renewals})


@member_required
def portal_renewal_apply(request):
    member = request.member
    vehicles = member.vehicles.filter(status__in=[VehicleStatus.ACTIVE, VehicleStatus.SUSPENDED, VehicleStatus.PENDING])
    document_types = DocumentType.objects.all().order_by('name')

    if request.method == 'POST':
        vehicle = vehicles.filter(id=request.POST.get('vehicle_id')).first()
        if not vehicle:
            messages.error(request, "Invalid vehicle selection.")
            return redirect('portal:renewal_apply')

        doc_type = document_types.filter(id=request.POST.get('document_type_id')).first()
        if not doc_type:
            messages.error(request, "Invalid regulatory document type.")
            return redirect('portal:renewal_apply')

        req = RenewalService.submit_renewal(
            member=member,
            vehicle=vehicle,
            document_type=doc_type,
            actor=request.user,
            notes=request.POST.get('notes', '').strip(),
        )
        messages.success(request, f"Renewal application {req.request_number} submitted! Secretariat officers will review and issue billing.")
        return redirect('portal:renewals')

    return _render_portal_mui(request, section='renewal-apply', title='Apply for Renewal')


@member_required
def portal_notifications(request):
    notifications = list(
        Notification.objects.filter(recipient_user=request.user)
        .order_by('-created_at')
        .values('id', 'title', 'message', 'status', 'created_at')
    )
    return _render_portal_mui(request, section='notifications', title='Notifications', portal_data={'notifications': notifications})


@member_required
def portal_notification_mark_read(request, notif_id):
    notif = Notification.objects.filter(id=notif_id).first()
    if not notif:
        raise Http404("Notification not found")
    if notif.recipient_user != request.user and notif.recipient_member != request.member:
        raise PermissionDenied("Access Denied.")

    notif.mark_as_read()
    messages.success(request, "Notification marked as read.")
    return redirect('portal:notifications')


@member_required
def portal_preferences(request):
    pref, _ = CommunicationPreference.objects.get_or_create(member=request.member)
    if request.method == 'POST':
        for field in (
            'sms_enabled', 'whatsapp_enabled', 'email_enabled', 'in_app_enabled',
            'compliance_alerts', 'billing_alerts', 'renewal_alerts', 'announcements',
        ):
            setattr(pref, field, field in request.POST)
        pref.save()
        messages.success(request, "Communication preferences updated successfully.")
        return redirect('portal:preferences')

    return _render_portal_mui(
        request,
        section='preferences',
        title='Communication Preferences',
        portal_data={
            'preferences': {
                'sms_enabled': pref.sms_enabled,
                'whatsapp_enabled': pref.whatsapp_enabled,
                'email_enabled': pref.email_enabled,
                'in_app_enabled': pref.in_app_enabled,
                'compliance_alerts': pref.compliance_alerts,
                'billing_alerts': pref.billing_alerts,
                'renewal_alerts': pref.renewal_alerts,
                'announcements': pref.announcements,
            }
        },
    )


@member_required
def portal_complaints(request):
    complaints = list(
        Incident.objects.filter(reported_by_member=request.member)
        .order_by('-created_at')
        .values('id', 'ticket_number', 'title', 'severity', 'status', 'created_at')
    )
    return _render_portal_mui(request, section='complaints', title='Complaints & Tickets', portal_data={'complaints': complaints})


@member_required
def portal_complaint_submit(request):
    member = request.member
    vehicles = member.vehicles.all()

    if request.method == 'POST':
        inc_type = request.POST.get('incident_type', IncidentType.COMPLAINT)
        severity = request.POST.get('severity', IncidentSeverity.MEDIUM)
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        location = request.POST.get('location', '').strip()
        vehicle_id = request.POST.get('vehicle_id')

        if not title or not description:
            messages.error(request, "Title and description are required.")
            return redirect('portal:complaint_submit')

        vehicle = vehicles.filter(id=vehicle_id).first() if vehicle_id else None
        inc = Incident.objects.create(
            reported_by_member=member,
            incident_type=inc_type,
            severity=severity,
            vehicle=vehicle,
            title=title,
            description=description,
            location=location,
            status=IncidentStatus.SUBMITTED,
        )
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.CREATE,
            entity_type='Incident',
            entity_id=inc.ticket_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Member submitted ticket {inc.ticket_number}: {title}",
        )
        messages.success(request, f"Ticket {inc.ticket_number} created! A SACCO officer has been notified.")
        return redirect('portal:complaints')

    return _render_portal_mui(request, section='complaint-submit', title='Submit Inquiry / Ticket')
