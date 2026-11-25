import io
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from fpdf.enums import XPos, YPos
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from nht_sacco.apps.members.models import Member, MembershipStatus
from nht_sacco.apps.vehicles.models import (
    Vehicle,
    VehicleStatus,
    VehicleComplianceCard,
    ComplianceCardStatus,
)
from nht_sacco.apps.documents.models import Document, VerificationStatus
from nht_sacco.apps.compliance.models import ComplianceStatus, ComplianceAlert
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.billing.models import Invoice
from nht_sacco.apps.payments.models import Payment, PaymentStatus, ManualPaymentVoucher
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.accounting.models import Expense
from nht_sacco.apps.routes.models import Route
from nht_sacco.apps.integrations.models import ConfigurationChangeRequest, ChangeRequestStatus
from nht_sacco.apps.integrations.branding import DocumentBrandingService, _sanitize_pdf_text


class ExecutiveDashboardMetrics:
    @classmethod
    def get_kpis(cls):
        # 1. Members
        member_agg = Member.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status=MembershipStatus.ACTIVE)),
            pending=Count('id', filter=Q(status=MembershipStatus.PENDING)),
            suspended=Count('id', filter=Q(status=MembershipStatus.SUSPENDED)),
        )
        total_members = member_agg['total'] or 0
        active_members = member_agg['active'] or 0
        pending_members = member_agg['pending'] or 0
        suspended_members = member_agg['suspended'] or 0

        # 2. Fleet & Compliance (prefetch documents to avoid N+1)
        total_vehicles = Vehicle.objects.count()
        active_vehicles_qs = Vehicle.objects.filter(status=VehicleStatus.ACTIVE).prefetch_related('compliance_documents__document_type')
        active_vehicles_count = active_vehicles_qs.count()
        pending_vehicles_count = Vehicle.objects.filter(status=VehicleStatus.PENDING).count()
        compliant_count = 0
        delinquent_count = 0
        for v in active_vehicles_qs:
            res = ComplianceService.check_vehicle_compliance(v)
            is_comp = (res.get('status') != ComplianceStatus.NON_COMPLIANT)
            if is_comp:
                compliant_count += 1
            else:
                delinquent_count += 1

        compliance_rate = (
            round((compliant_count / total_vehicles) * 100, 1) if total_vehicles > 0 else 100.0
        )

        # 3. Documents & Compliance Cards
        now_date = timezone.localdate()
        in_30_days = now_date + timezone.timedelta(days=30)
        expiring_docs = Document.objects.filter(
            status=VerificationStatus.VERIFIED,
            expiry_date__gte=now_date,
            expiry_date__lte=in_30_days
        ).count()
        expired_docs = Document.objects.filter(
            Q(status=VerificationStatus.EXPIRED) | Q(expiry_date__lt=now_date)
        ).count()

        expiring_cards = VehicleComplianceCard.objects.filter(
            status=ComplianceCardStatus.VALID,
            expiry_date__gte=now_date,
            expiry_date__lte=in_30_days,
        ).count()
        expired_cards = VehicleComplianceCard.objects.filter(
            Q(status=ComplianceCardStatus.EXPIRED)
            | Q(status=ComplianceCardStatus.VALID, expiry_date__lt=now_date)
        ).count()

        # 4. Financials
        total_invoiced = Invoice.objects.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        total_collected = Payment.objects.filter(status=PaymentStatus.SUCCESS).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        total_outstanding = total_invoiced - total_collected
        if total_outstanding < Decimal('0.00'):
            total_outstanding = Decimal('0.00')

        total_expenses = Expense.objects.filter(status='APPROVED').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        net_cash = total_collected - total_expenses

        # 5. Route Distribution & Active Routes
        active_routes_count = Route.objects.filter(is_active=True).count()
        routes_qs = Route.objects.annotate(
            vehicle_count=Count('allocated_vehicles', filter=Q(allocated_vehicles__is_active=True))
        ).order_by('-vehicle_count')
        route_distribution = [
            {'name': r.name, 'code': r.route_code, 'count': r.vehicle_count}
            for r in routes_qs[:5]
        ]

        # 6. Pending approvals & system alerts
        pending_vouchers = ManualPaymentVoucher.objects.filter(status=ManualPaymentVoucher.Status.PENDING).count()
        pending_renewals = RenewalRequest.objects.filter(
            status__in=[RenewalStatus.SUBMITTED, RenewalStatus.UNDER_REVIEW]
        ).count()
        pending_config_crs = ConfigurationChangeRequest.objects.filter(status=ChangeRequestStatus.PENDING).count()
        unresolved_alerts = ComplianceAlert.objects.filter(is_resolved=False).count()

        return {
            'total_members': total_members,
            'active_members': active_members,
            'pending_members': pending_members,
            'suspended_members': suspended_members,
            'total_vehicles': total_vehicles,
            'active_vehicles': active_vehicles_count,
            'vehicles_awaiting_compliance': pending_vehicles_count + delinquent_count,
            'compliant_vehicles': compliant_count,
            'delinquent_vehicles': delinquent_count,
            'compliance_rate': compliance_rate,
            'expiring_docs': expiring_docs,
            'expired_docs': expired_docs,
            'expiring_certificates': expiring_cards,
            'expired_certificates': expired_cards,
            'active_routes': active_routes_count,
            'total_invoiced': total_invoiced,
            'total_collected': total_collected,
            'total_outstanding': total_outstanding,
            'total_expenses': total_expenses,
            'net_cash': net_cash,
            'route_distribution': route_distribution,
            'system_alerts': unresolved_alerts,
            'pending_approvals': pending_members + pending_vouchers + pending_renewals + pending_config_crs,
        }


class ReportExportService:
    @classmethod
    def generate_compliance_pdf(cls) -> bytes:
        """
        Generates official SACCO Fleet Compliance Audit PDF Report using centralized
        DocumentBrandingService (proportional logo + company profile + page numbers).
        """
        pdf, ctx = DocumentBrandingService.create_pdf(orientation='P', format='A4')
        DocumentBrandingService.apply_pdf_header(
            pdf,
            ctx,
            title="FLEET COMPLIANCE AUDIT REPORT",
            subtitle="Report Scope: All Registered Vehicles",
        )

        # Table Header
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(25, 7, "PLATE NO", border=1, fill=True)
        pdf.cell(35, 7, "CATEGORY", border=1, fill=True)
        pdf.cell(45, 7, "OWNER / MEMBER", border=1, fill=True)
        pdf.cell(45, 7, "APPROVED ROUTE", border=1, fill=True)
        pdf.cell(25, 7, "COMPLIANCE", border=1, fill=True, align='C')
        pdf.cell(15, 7, "STATUS", border=1, fill=True, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Table Rows (optimized prefetch)
        pdf.set_font('Helvetica', '', 8)
        vehicles = Vehicle.objects.select_related('current_owner').prefetch_related(
            'route_allocations__route',
            'compliance_documents__document_type',
        ).order_by('registration_number')

        for v in vehicles:
            comp = ComplianceService.check_vehicle_compliance(v)
            is_comp = (comp.get('status') != ComplianceStatus.NON_COMPLIANT)
            comp_label = "COMPLIANT" if is_comp else "DELINQUENT"
            owner_name = v.current_owner.full_name if v.current_owner else "N/A"
            active_alloc = next((ra for ra in v.route_allocations.all() if ra.is_active), None)
            route_name = active_alloc.route.name if (active_alloc and active_alloc.route) else "Unassigned"

            pdf.cell(25, 6, _sanitize_pdf_text(v.registration_number), border=1)
            pdf.cell(35, 6, _sanitize_pdf_text(v.get_category_display()[:20]), border=1)
            pdf.cell(45, 6, _sanitize_pdf_text(owner_name[:24]), border=1)
            pdf.cell(45, 6, _sanitize_pdf_text(route_name[:24]), border=1)

            if is_comp:
                pdf.set_text_color(22, 101, 52)
            else:
                pdf.set_text_color(185, 28, 28)
            pdf.cell(25, 6, comp_label, border=1, align='C')

            pdf.set_text_color(30, 41, 59)
            pdf.cell(15, 6, _sanitize_pdf_text(v.status[:6]), border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output())

    @classmethod
    def generate_financial_excel(cls) -> bytes:
        """
        Generates official multi-sheet Financial Summary Excel workbook via openpyxl
        with centralized proportional logo embedding, branded headers, and editable formulas.
        """
        wb = openpyxl.Workbook()

        # Sheet 1: Invoices
        ws_inv = wb.active
        ws_inv.title = "Invoices"

        headers_inv = [
            "Invoice No", "Member Name", "Membership No", "Issue Date", "Due Date",
            "Subtotal (KES)", "Statutory (KES)", "Total Amount (KES)", "Amount Paid (KES)", "Status"
        ]
        inv_start_row = DocumentBrandingService.apply_excel_header(
            ws_inv,
            title="SACCO FINANCIAL SUMMARY — INVOICES LEDGER",
            col_count=len(headers_inv),
            subtitle="Invoices & Statutory Pass-Through Breakdown",
        )

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="10315C", end_color="10315C", fill_type="solid")
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        for col_idx, h_label in enumerate(headers_inv, start=1):
            cell = ws_inv.cell(row=inv_start_row, column=col_idx, value=h_label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        invoices = Invoice.objects.select_related('member').order_by('-created_at')
        row_cursor = inv_start_row + 1
        for inv in invoices:
            values = [
                inv.invoice_number,
                inv.member.full_name if inv.member else "N/A",
                inv.member.membership_number if inv.member else "N/A",
                str(inv.issue_date),
                str(inv.due_date),
                float(inv.subtotal),
                float(inv.statutory_total),
                float(inv.total_amount),
                float(inv.amount_paid),
                inv.get_status_display(),
            ]
            for col_idx, val in enumerate(values, start=1):
                c = ws_inv.cell(row=row_cursor, column=col_idx, value=val)
                c.border = border_thin
                if col_idx in (6, 7, 8, 9):
                    c.number_format = '#,##0.00'
            row_cursor += 1

        if row_cursor > inv_start_row + 1:
            total_cell = ws_inv.cell(row=row_cursor, column=5, value="TOTALS")
            total_cell.font = Font(name="Calibri", size=10, bold=True)
            for col_idx, col_letter in ((6, 'F'), (7, 'G'), (8, 'H'), (9, 'I')):
                sum_cell = ws_inv.cell(
                    row=row_cursor,
                    column=col_idx,
                    value=f"=SUM({col_letter}{inv_start_row + 1}:{col_letter}{row_cursor - 1})",
                )
                sum_cell.font = Font(name="Calibri", size=10, bold=True)
                sum_cell.number_format = '#,##0.00'

        # Sheet 2: Payments / Receipts
        ws_pay = wb.create_sheet(title="Receipts & Payments")
        headers_pay = ["Receipt / Trans ID", "Invoice Ref", "Member Name", "Payment Method", "Amount Cleared (KES)", "Confirmed At", "Status"]
        pay_start_row = DocumentBrandingService.apply_excel_header(
            ws_pay,
            title="SACCO FINANCIAL SUMMARY — CLEARED PAYMENTS & RECEIPTS",
            col_count=len(headers_pay),
            subtitle="Confirmed Settlements",
        )
        for col_idx, h_label in enumerate(headers_pay, start=1):
            cell = ws_pay.cell(row=pay_start_row, column=col_idx, value=h_label)
            cell.font = header_font
            cell.fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = border_thin

        payments = Payment.objects.select_related('invoice', 'member').filter(status=PaymentStatus.SUCCESS).order_by('-created_at')
        pay_row = pay_start_row + 1
        for p in payments:
            values = [
                p.provider_transaction_id or p.payment_reference,
                p.invoice.invoice_number if p.invoice else "N/A",
                p.member.full_name if p.member else "N/A",
                p.get_method_display(),
                float(p.amount),
                p.confirmed_at.strftime("%Y-%m-%d %H:%M") if p.confirmed_at else "",
                p.get_status_display(),
            ]
            for col_idx, val in enumerate(values, start=1):
                c = ws_pay.cell(row=pay_row, column=col_idx, value=val)
                c.border = border_thin
                if col_idx == 5:
                    c.number_format = '#,##0.00'
            pay_row += 1

        if pay_row > pay_start_row + 1:
            ws_pay.cell(row=pay_row, column=4, value="TOTAL CLEARED").font = Font(name="Calibri", size=10, bold=True)
            tot_p = ws_pay.cell(row=pay_row, column=5, value=f"=SUM(E{pay_start_row + 1}:E{pay_row - 1})")
            tot_p.font = Font(name="Calibri", size=10, bold=True)
            tot_p.number_format = '#,##0.00'

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
