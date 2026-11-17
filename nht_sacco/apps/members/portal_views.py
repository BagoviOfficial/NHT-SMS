import logging
from decimal import Decimal
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.members.models import Member, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus, VehicleCategory, FuelType
from nht_sacco.apps.documents.models import Document, DocumentType
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus, Receipt
from nht_sacco.apps.payments.daraja import DarajaClient
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.notifications.models import (
    Notification,
    NotificationStatus,
    CommunicationPreference,
    Announcement,
    NotificationChannel,
)
from nht_sacco.apps.incidents.models import Incident, IncidentType, IncidentSeverity, IncidentStatus
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

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
                notes=f"Non-member user {request.user.username} (role: {request.user.role}) denied access to member portal."
            )
            raise PermissionDenied("Access Denied: Only registered SACCO members can access the Member Portal.")

        member = request.user.member_profile
        if member.status == MembershipStatus.TERMINATED:
            raise PermissionDenied("Access Denied: Your membership has been terminated. Contact SACCO Secretariat.")

        request.member = member
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@member_required
def portal_dashboard(request):
    member = request.member
    vehicles = member.vehicles.all()
    
    # Compute fleet compliance counts
    total_vehicles = vehicles.count()
    compliant_count = 0
    expiring_soon_count = 0
    non_compliant_count = 0
    
    for v in vehicles:
        comp = ComplianceService.check_vehicle_compliance(v)
        st = comp['status']
        if st == 'FULLY_COMPLIANT':
            compliant_count += 1
        elif st == 'EXPIRING_SOON':
            expiring_soon_count += 1
        else:
            non_compliant_count += 1

    # Financial Summary
    invoices = member.invoices.all()
    total_invoiced = invoices.aggregate(s=Sum('total_amount'))['s'] or Decimal('0.00')
    total_paid = invoices.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00')
    balance_due = total_invoiced - total_paid

    # Recent Data
    recent_invoices = invoices.order_by('-issue_date')[:5]
    recent_notifications = Notification.objects.filter(
        recipient_user=request.user
    ).order_by('-created_at')[:5]
    
    announcements = Announcement.objects.filter(is_published=True).order_by('-created_at')[:3]

    context = {
        'member': member,
        'total_vehicles': total_vehicles,
        'compliant_count': compliant_count,
        'expiring_soon_count': expiring_soon_count,
        'non_compliant_count': non_compliant_count,
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'balance_due': balance_due,
        'recent_invoices': recent_invoices,
        'recent_notifications': recent_notifications,
        'announcements': announcements,
        'active_tab': 'dashboard',
    }
    return render(request, 'portal/dashboard.html', context)


@member_required
def portal_vehicles(request):
    member = request.member
    vehicles_data = []
    for v in member.vehicles.all().order_by('registration_number'):
        comp = ComplianceService.check_vehicle_compliance(v)
        vehicles_data.append({
            'vehicle': v,
            'compliance': comp,
        })

    context = {
        'member': member,
        'vehicles_data': vehicles_data,
        'active_tab': 'vehicles',
    }
    return render(request, 'portal/vehicles_list.html', context)


@member_required
def portal_vehicle_detail(request, vehicle_id):
    # Anti-IDOR: verify vehicle ownership
    vehicle = Vehicle.objects.filter(id=vehicle_id).first()
    if not vehicle:
        raise Http404("Vehicle not found")
    if vehicle.current_owner != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.VIEW,
            entity_type='Vehicle',
            entity_id=vehicle.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR Security Violation: User {request.user.username} attempted to access vehicle {vehicle.registration_number} owned by another member."
        )
        raise PermissionDenied("Access Denied: You do not own this vehicle.")

    comp = ComplianceService.check_vehicle_compliance(vehicle)
    documents = Document.objects.filter(vehicle=vehicle).select_related('document_type').order_by('-issue_date')

    context = {
        'member': request.member,
        'vehicle': vehicle,
        'compliance': comp,
        'documents': documents,
        'active_tab': 'vehicles',
    }
    return render(request, 'portal/vehicle_detail.html', context)


@member_required
def portal_vehicle_card(request, vehicle_id):
    vehicle = Vehicle.objects.filter(id=vehicle_id).first()
    if not vehicle:
        raise Http404("Vehicle not found")
    if vehicle.current_owner != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.VIEW,
            entity_type='VehicleCard',
            entity_id=vehicle.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR violation on vehicle card: {vehicle.registration_number}"
        )
        raise PermissionDenied("Access Denied: You do not own this vehicle.")

    comp = ComplianceService.check_vehicle_compliance(vehicle)
    verify_url = request.build_absolute_uri(f"/verify/vehicle/{vehicle.qr_token}/")

    context = {
        'member': request.member,
        'vehicle': vehicle,
        'compliance': comp,
        'verify_url': verify_url,
    }
    return render(request, 'portal/vehicle_card.html', context)


@member_required
def portal_vehicle_register(request):
    if request.method == 'POST':
        reg_num = request.POST.get('registration_number', '').strip().upper()
        chassis = request.POST.get('chassis_number', '').strip().upper()
        engine = request.POST.get('engine_number', '').strip().upper()
        make = request.POST.get('make', '').strip()
        model_name = request.POST.get('model', '').strip()
        year = request.POST.get('year_of_manufacture', '').strip()
        category = request.POST.get('category', VehicleCategory.MATATU_14)
        fuel_type = request.POST.get('fuel_type', FuelType.DIESEL)
        capacity = request.POST.get('carrying_capacity', '14')

        if not reg_num or not chassis or not engine or not make or not model_name:
            messages.error(request, "All required vehicle fields must be provided.")
            return redirect('portal:vehicle_register')

        if Vehicle.objects.filter(registration_number=reg_num).exists():
            messages.error(request, f"Vehicle plate {reg_num} is already registered in the system.")
            return redirect('portal:vehicle_register')

        try:
            v = Vehicle.objects.create(
                registration_number=reg_num,
                chassis_number=chassis,
                engine_number=engine,
                make=make,
                model=model_name,
                year_of_manufacture=int(year) if year.isdigit() else timezone.now().year,
                category=category,
                fuel_type=fuel_type,
                carrying_capacity=int(capacity) if capacity.isdigit() else 14,
                current_owner=request.member,
                status=VehicleStatus.PENDING,
                created_by=request.user
            )
            AuditLog.log_action(
                actor=request.user,
                action=AuditAction.CREATE,
                entity_type='Vehicle',
                entity_id=v.id,
                outcome=AuditOutcome.SUCCESS,
                notes=f"Member submitted new vehicle {reg_num} for onboarding."
            )
            messages.success(request, f"Vehicle {reg_num} submitted successfully. It is currently pending Secretariat verification.")
            return redirect('portal:vehicles')
        except Exception as e:
            messages.error(request, f"Failed to register vehicle: {str(e)}")
            return redirect('portal:vehicle_register')

    context = {
        'member': request.member,
        'categories': VehicleCategory.choices,
        'fuel_types': FuelType.choices,
        'active_tab': 'vehicles',
    }
    return render(request, 'portal/vehicle_register.html', context)


@member_required
def portal_invoices(request):
    invoices = request.member.invoices.all().select_related('vehicle').order_by('-issue_date')
    context = {
        'member': request.member,
        'invoices': invoices,
        'active_tab': 'invoices',
    }
    return render(request, 'portal/invoices_list.html', context)


@member_required
def portal_invoice_detail(request, invoice_id):
    invoice = Invoice.objects.filter(id=invoice_id).select_related('member', 'vehicle').first()
    if not invoice:
        raise Http404("Invoice not found")
    if invoice.member != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.VIEW,
            entity_type='Invoice',
            entity_id=invoice.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR violation: Member attempted to access invoice {invoice.invoice_number} of another member."
        )
        raise PermissionDenied("Access Denied: You do not own this invoice.")

    items = invoice.items.select_related('service_item').all()
    payments = invoice.payments.filter(status=PaymentStatus.SUCCESS).order_by('-created_at')

    context = {
        'member': request.member,
        'invoice': invoice,
        'items': items,
        'payments': payments,
        'active_tab': 'invoices',
    }
    return render(request, 'portal/invoice_detail.html', context)


@member_required
def portal_invoice_pay_stk(request, invoice_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    invoice = Invoice.objects.filter(id=invoice_id).first()
    if not invoice:
        return JsonResponse({'error': 'Invoice not found'}, status=404)
    if invoice.member != request.member:
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='Invoice',
            entity_id=invoice.id,
            outcome=AuditOutcome.DENIED,
            notes=f"IDOR attack on payment trigger: Invoice {invoice.invoice_number}"
        )
        raise PermissionDenied("Access Denied: You do not own this invoice.")

    phone = request.POST.get('phone_number', request.member.phone_number)
    if invoice.is_fully_paid:
        return JsonResponse({'error': 'Invoice is already settled in full.'}, status=400)

    try:
        daraja = DarajaClient()
        res = daraja.initiate_stk_push(
            phone_number=phone,
            amount=invoice.balance_due,
            account_reference=invoice.invoice_number,
            transaction_desc=f"NHT SACCO {invoice.invoice_number}"
        )
        if res.get('ResponseCode') == '0':
            messages.success(request, f"M-Pesa STK Push prompted to {phone}. Enter your PIN to complete settlement.")
            return redirect('portal:invoice_detail', invoice_id=invoice.id)
        else:
            messages.error(request, f"M-Pesa Error: {res.get('CustomerMessage', 'Failed to prompt phone.')}")
            return redirect('portal:invoice_detail', invoice_id=invoice.id)
    except Exception as e:
        messages.error(request, f"STK Push error: {str(e)}")
        return redirect('portal:invoice_detail', invoice_id=invoice.id)


@member_required
def portal_receipts(request):
    receipts = Receipt.objects.filter(
        payment__invoice__member=request.member
    ).select_related('payment', 'payment__invoice').order_by('-issued_at')
    
    context = {
        'member': request.member,
        'receipts': receipts,
        'active_tab': 'invoices',
    }
    return render(request, 'portal/receipts_list.html', context)


@member_required
def portal_statement(request):
    member = request.member
    invoices = member.invoices.all().order_by('issue_date', 'created_at')
    payments = Payment.objects.filter(
        invoice__member=member,
        status=PaymentStatus.SUCCESS
    ).select_related('invoice').order_by('confirmed_at', 'created_at')

    # Merge into chronological timeline
    ledger_entries = []
    for inv in invoices:
        ledger_entries.append({
            'date': inv.issue_date,
            'timestamp': inv.created_at,
            'type': 'INVOICE',
            'reference': inv.invoice_number,
            'description': f"Invoice for {inv.vehicle.registration_number if inv.vehicle else 'SACCO Services'}",
            'debit': inv.total_amount,
            'credit': Decimal('0.00'),
        })

    for p in payments:
        ledger_entries.append({
            'date': (p.confirmed_at.date() if p.confirmed_at else p.created_at.date()),
            'timestamp': p.confirmed_at or p.created_at,
            'type': 'PAYMENT',
            'reference': p.provider_transaction_id or p.payment_reference,
            'description': f"Settlement towards {p.invoice.invoice_number} ({p.get_method_display()})",
            'debit': Decimal('0.00'),
            'credit': p.amount,
        })

    # Sort chronologically
    ledger_entries.sort(key=lambda x: (x['date'], x['timestamp']))

    # Compute running balance
    running_bal = Decimal('0.00')
    total_debits = Decimal('0.00')
    total_credits = Decimal('0.00')

    for entry in ledger_entries:
        running_bal += (entry['debit'] - entry['credit'])
        entry['running_balance'] = running_bal
        total_debits += entry['debit']
        total_credits += entry['credit']

    context = {
        'member': member,
        'entries': ledger_entries,
        'total_debits': total_debits,
        'total_credits': total_credits,
        'current_balance': running_bal,
        'statement_date': timezone.now(),
        'active_tab': 'statement',
    }
    return render(request, 'portal/statement.html', context)


@member_required
def portal_renewals(request):
    renewals = RenewalRequest.objects.filter(
        member=request.member
    ).select_related('vehicle', 'document_type', 'invoice').order_by('-created_at')

    context = {
        'member': request.member,
        'renewals': renewals,
        'active_tab': 'renewals',
    }
    return render(request, 'portal/renewal_list.html', context)


@member_required
def portal_renewal_apply(request):
    member = request.member
    vehicles = member.vehicles.filter(status__in=[VehicleStatus.ACTIVE, VehicleStatus.SUSPENDED, VehicleStatus.PENDING])
    document_types = DocumentType.objects.all().order_by('name')

    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle_id')
        doc_type_id = request.POST.get('document_type_id')
        notes = request.POST.get('notes', '').strip()

        vehicle = vehicles.filter(id=vehicle_id).first()
        if not vehicle:
            messages.error(request, "Invalid vehicle selection.")
            return redirect('portal:renewal_apply')

        doc_type = document_types.filter(id=doc_type_id).first()
        if not doc_type:
            messages.error(request, "Invalid regulatory document type.")
            return redirect('portal:renewal_apply')

        # Find existing document if any
        current_doc = Document.objects.filter(vehicle=vehicle, document_type=doc_type).order_by('-expiry_date').first()

        req = RenewalRequest.objects.create(
            member=member,
            vehicle=vehicle,
            document_type=doc_type,
            current_document=current_doc,
            status=RenewalStatus.SUBMITTED,
            notes=notes
        )

        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.CREATE,
            entity_type='RenewalRequest',
            entity_id=req.id,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Member submitted renewal {req.request_number} for {vehicle.registration_number} ({doc_type.name})"
        )
        messages.success(request, f"Renewal application {req.request_number} submitted! Secretariat officers will review and issue billing.")
        return redirect('portal:renewals')

    context = {
        'member': member,
        'vehicles': vehicles,
        'document_types': document_types,
        'active_tab': 'renewals',
    }
    return render(request, 'portal/renewal_apply.html', context)


@member_required
def portal_notifications(request):
    notifications = Notification.objects.filter(
        recipient_user=request.user
    ).order_by('-created_at')

    context = {
        'member': request.member,
        'notifications': notifications,
        'active_tab': 'notifications',
    }
    return render(request, 'portal/notifications.html', context)


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
        pref.sms_enabled = 'sms_enabled' in request.POST
        pref.whatsapp_enabled = 'whatsapp_enabled' in request.POST
        pref.email_enabled = 'email_enabled' in request.POST
        pref.in_app_enabled = 'in_app_enabled' in request.POST
        pref.compliance_alerts = 'compliance_alerts' in request.POST
        pref.billing_alerts = 'billing_alerts' in request.POST
        pref.renewal_alerts = 'renewal_alerts' in request.POST
        pref.announcements = 'announcements' in request.POST
        pref.save()

        messages.success(request, "Communication preferences updated successfully.")
        return redirect('portal:preferences')

    context = {
        'member': request.member,
        'preferences': pref,
        'active_tab': 'preferences',
    }
    return render(request, 'portal/preferences.html', context)


@member_required
def portal_complaints(request):
    complaints = Incident.objects.filter(
        reported_by_member=request.member
    ).order_by('-created_at')

    context = {
        'member': request.member,
        'complaints': complaints,
        'active_tab': 'complaints',
    }
    return render(request, 'portal/complaints.html', context)


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
            status=IncidentStatus.SUBMITTED
        )

        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.CREATE,
            entity_type='Incident',
            entity_id=inc.id,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Member submitted ticket {inc.ticket_number}: {title}"
        )
        messages.success(request, f"Ticket {inc.ticket_number} created! A SACCO officer has been notified.")
        return redirect('portal:complaints')

    context = {
        'member': member,
        'vehicles': vehicles,
        'incident_types': IncidentType.choices,
        'severities': IncidentSeverity.choices,
        'active_tab': 'complaints',
    }
    return render(request, 'portal/complaint_submit.html', context)
