import io
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q
from fpdf import FPDF
from fpdf.enums import XPos, YPos
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from nht_sacco.apps.members.models import Member, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus
from nht_sacco.apps.documents.models import Document, VerificationStatus
from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus
from nht_sacco.apps.accounting.models import Expense
from nht_sacco.apps.routes.models import Route


class ExecutiveDashboardMetrics:
    @classmethod
    def get_kpis(cls):
        # 1. Members
        total_members = Member.objects.count()
        active_members = Member.objects.filter(status=MembershipStatus.ACTIVE).count()
        pending_members = Member.objects.filter(status=MembershipStatus.PENDING).count()

        # 2. Fleet & Compliance
        total_vehicles = Vehicle.objects.count()
        active_vehicles = Vehicle.objects.filter(status=VehicleStatus.ACTIVE)
        compliant_count = 0
        delinquent_count = 0
        for v in active_vehicles:
            res = ComplianceService.check_vehicle_compliance(v)
            is_comp = (res.get('status') != ComplianceStatus.NON_COMPLIANT)
            if is_comp:
                compliant_count += 1
            else:
                delinquent_count += 1

        compliance_rate = (
            round((compliant_count / total_vehicles) * 100, 1) if total_vehicles > 0 else 100.0
        )

        # 3. Documents
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

        # 4. Financials
        total_invoiced = Invoice.objects.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        total_collected = Payment.objects.filter(status=PaymentStatus.SUCCESS).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        total_outstanding = total_invoiced - total_collected
        if total_outstanding < Decimal('0.00'):
            total_outstanding = Decimal('0.00')

        total_expenses = Expense.objects.filter(status='APPROVED').aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        net_cash = total_collected - total_expenses

        # 5. Route Distribution
        routes_qs = Route.objects.annotate(
            vehicle_count=Count('allocated_vehicles', filter=Q(allocated_vehicles__is_active=True))
        ).order_by('-vehicle_count')
        route_distribution = [
            {'name': r.name, 'code': r.route_code, 'count': r.vehicle_count}
            for r in routes_qs[:5]
        ]

        return {
            'total_members': total_members,
            'active_members': active_members,
            'pending_members': pending_members,
            'total_vehicles': total_vehicles,
            'compliant_vehicles': compliant_count,
            'delinquent_vehicles': delinquent_count,
            'compliance_rate': compliance_rate,
            'expiring_docs': expiring_docs,
            'expired_docs': expired_docs,
            'total_invoiced': total_invoiced,
            'total_collected': total_collected,
            'total_outstanding': total_outstanding,
            'total_expenses': total_expenses,
            'net_cash': net_cash,
            'route_distribution': route_distribution,
        }


class ReportExportService:
    @classmethod
    def generate_compliance_pdf(cls) -> bytes:
        """
        Generates official SACCO Fleet Compliance Audit PDF Report using fpdf2.
        """
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Header Band (Brand Navy: #10315C -> RGB: 16, 49, 92)
        pdf.set_fill_color(16, 49, 92)
        pdf.rect(0, 0, 210, 28, 'F')

        pdf.set_font('Helvetica', 'B', 15)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(10, 6)
        pdf.cell(190, 8, "NORTHERN HIGHWAYS TRANSPORTERS SACCO", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(255, 138, 0)  # Accent Gold #FF8A00
        pdf.cell(190, 6, "FLEET COMPLIANCE AUDIT REPORT", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')

        pdf.ln(12)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font('Helvetica', '', 9)
        gen_time = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S EAT")
        pdf.cell(100, 6, f"Generated On: {gen_time}", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(90, 6, f"Report Scope: All Active Registered Vehicles", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        pdf.line(10, 42, 200, 42)
        pdf.ln(4)

        # Table Header
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(241, 245, 249)
        pdf.cell(25, 7, "PLATE NO", border=1, fill=True)
        pdf.cell(35, 7, "CATEGORY", border=1, fill=True)
        pdf.cell(45, 7, "OWNER / MEMBER", border=1, fill=True)
        pdf.cell(45, 7, "APPROVED ROUTE", border=1, fill=True)
        pdf.cell(25, 7, "COMPLIANCE", border=1, fill=True, align='C')
        pdf.cell(15, 7, "STATUS", border=1, fill=True, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Table Rows
        pdf.set_font('Helvetica', '', 8)
        vehicles = Vehicle.objects.select_related('current_owner').prefetch_related('route_allocations__route').order_by('registration_number')
        
        for v in vehicles:
            comp = ComplianceService.check_vehicle_compliance(v)
            is_comp = (comp.get('status') != ComplianceStatus.NON_COMPLIANT)
            comp_label = "COMPLIANT" if is_comp else "DELINQUENT"
            owner_name = v.current_owner.full_name if v.current_owner else "N/A"
            active_alloc = v.route_allocations.filter(is_active=True).first()
            route_name = active_alloc.route.name if (active_alloc and active_alloc.route) else "Unassigned"

            pdf.cell(25, 6, v.registration_number, border=1)
            pdf.cell(35, 6, v.get_category_display()[:20], border=1)
            pdf.cell(45, 6, owner_name[:24], border=1)
            pdf.cell(45, 6, route_name[:24], border=1)
            
            # Badge colour
            if is_comp:
                pdf.set_text_color(22, 101, 52)  # green
            else:
                pdf.set_text_color(185, 28, 28)  # red
            pdf.cell(25, 6, comp_label, border=1, align='C')
            
            pdf.set_text_color(30, 41, 59)
            pdf.cell(15, 6, v.status[:6], border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Footer
        pdf.set_y(-15)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(0, 10, "NHT-SMS ERP System | Confidential SACCO Internal Document", align='C')

        return bytes(pdf.output())

    @classmethod
    def generate_financial_excel(cls) -> bytes:
        """
        Generates official multi-sheet Financial Summary Excel workbook via openpyxl.
        """
        wb = openpyxl.Workbook()
        
        # Sheet 1: Invoices
        ws_inv = wb.active
        ws_inv.title = "Invoices"

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="10315C", end_color="10315C", fill_type="solid")
        border_thin = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        headers_inv = ["Invoice No", "Member Name", "Membership No", "Issue Date", "Due Date", "Subtotal (KES)", "Statutory (KES)", "Total Amount (KES)", "Amount Paid (KES)", "Status"]
        ws_inv.append(headers_inv)
        for col_idx in range(1, len(headers_inv) + 1):
            cell = ws_inv.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        invoices = Invoice.objects.select_related('member').order_by('-created_at')
        for inv in invoices:
            ws_inv.append([
                inv.invoice_number,
                inv.member.full_name if inv.member else "N/A",
                inv.member.membership_number if inv.member else "N/A",
                str(inv.issue_date),
                str(inv.due_date),
                float(inv.subtotal),
                float(inv.statutory_total),
                float(inv.total_amount),
                float(inv.amount_paid),
                inv.get_status_display()
            ])

        # Sheet 2: Payments / Receipts
        ws_pay = wb.create_sheet(title="Receipts & Payments")
        headers_pay = ["Receipt / Trans ID", "Invoice Ref", "Member Name", "Payment Method", "Amount Cleared (KES)", "Confirmed At", "Status"]
        ws_pay.append(headers_pay)
        for col_idx in range(1, len(headers_pay) + 1):
            cell = ws_pay.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = PatternFill(start_color="0284C7", end_color="0284C7", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")

        payments = Payment.objects.select_related('invoice', 'member').filter(status=PaymentStatus.SUCCESS).order_by('-created_at')
        for p in payments:
            ws_pay.append([
                p.provider_transaction_id or p.payment_reference,
                p.invoice.invoice_number if p.invoice else "N/A",
                p.member.full_name if p.member else "N/A",
                p.get_method_display(),
                float(p.amount),
                p.confirmed_at.strftime("%Y-%m-%d %H:%M") if p.confirmed_at else "",
                p.get_status_display()
            ])

        # Save to buffer
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
