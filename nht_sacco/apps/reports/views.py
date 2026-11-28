from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.accounts.permissions import FINANCE_CHECKER_ROLES, MANAGEMENT_ROLES
from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.config.mui import render_mui_app
from .services import ReportExportService


FINANCE_EXPORT_ROLES = FINANCE_CHECKER_ROLES | {UserRole.AUDITOR}


def staff_role_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in MANAGEMENT_ROLES):
            AuditLog.log_action(
                actor=request.user,
                action=AuditAction.VIEW,
                entity_type='ExecutiveReports',
                outcome=AuditOutcome.DENIED,
                notes=f"Unauthorized access attempt to executive reporting by user {request.user.username} (Role: {request.user.role})",
            )
            raise PermissionDenied("Access Denied: SACCO administrative clearance required.")
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_role_required
def reports_dashboard(request):
    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.VIEW,
        entity_type='ExecutiveDashboard',
        outcome=AuditOutcome.SUCCESS,
        notes="Viewed Executive SACCO Analytics Dashboard",
    )
    return render_mui_app(
        request,
        initial_route='reports',
        page_title='Executive Reports & Exports',
    )


@staff_role_required
def export_compliance_pdf(request):
    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.EXPORT,
        entity_type='CompliancePDFReport',
        outcome=AuditOutcome.SUCCESS,
        notes="Generated and exported Fleet Compliance Audit PDF",
    )
    pdf_bytes = ReportExportService.generate_compliance_pdf()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="NHT_Fleet_Compliance_Report.pdf"'
    return response


@login_required
def export_financial_excel(request):
    if not (request.user.is_superuser or request.user.role in FINANCE_EXPORT_ROLES):
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.EXPORT,
            entity_type='FinancialExcelReport',
            outcome=AuditOutcome.DENIED,
            notes=f"Unauthorized financial export attempt by user {request.user.username}",
        )
        raise PermissionDenied("Access Denied: Financial Officer authorization required.")

    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.EXPORT,
        entity_type='FinancialExcelReport',
        outcome=AuditOutcome.SUCCESS,
        notes="Generated and exported SACCO Financial Summary Excel",
    )
    excel_bytes = ReportExportService.generate_financial_excel()
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="NHT_Financial_Summary.xlsx"'
    return response
