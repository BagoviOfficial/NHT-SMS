from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
from .services import ExecutiveDashboardMetrics, ReportExportService
from nht_sacco.apps.governance.services import GovernanceService
from nht_sacco.apps.maintenance.services import MaintenanceService


AUTHORIZED_STAFF_ROLES = [
    UserRole.SUPER_ADMIN,
    UserRole.CHAIRMAN,
    UserRole.SECRETARY,
    UserRole.TREASURER,
    UserRole.ACCOUNTANT,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.RENEWAL_OFFICER,
    UserRole.FIELD_OFFICER,
    UserRole.AUDITOR,
]

FINANCE_STAFF_ROLES = [
    UserRole.SUPER_ADMIN,
    UserRole.CHAIRMAN,
    UserRole.TREASURER,
    UserRole.ACCOUNTANT,
    UserRole.AUDITOR,
]


def staff_role_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in AUTHORIZED_STAFF_ROLES):
            AuditLog.log_action(
                actor=request.user,
                action=AuditAction.VIEW,
                entity_type='ExecutiveReports',
                outcome=AuditOutcome.DENIED,
                notes=f"Unauthorized access attempt to executive reporting by user {request.user.username} (Role: {request.user.role})"
            )
            raise PermissionDenied("Access Denied: SACCO administrative clearance required.")
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_role_required
def reports_dashboard(request):
    kpis = ExecutiveDashboardMetrics.get_kpis()
    gov_summary = GovernanceService.get_governance_summary()
    maint_summary = MaintenanceService.get_fleet_maintenance_metrics()

    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.VIEW,
        entity_type='ExecutiveDashboard',
        outcome=AuditOutcome.SUCCESS,
        notes="Viewed Executive SACCO Analytics Dashboard"
    )

    context = {
        'kpis': kpis,
        'gov': gov_summary,
        'maintenance': maint_summary,
    }
    return render(request, 'reports/dashboard.html', context)


@staff_role_required
def export_compliance_pdf(request):
    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.EXPORT,
        entity_type='CompliancePDFReport',
        outcome=AuditOutcome.SUCCESS,
        notes="Generated and exported Fleet Compliance Audit PDF"
    )
    pdf_bytes = ReportExportService.generate_compliance_pdf()
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="NHT_Fleet_Compliance_Report.pdf"'
    return response


@login_required
def export_financial_excel(request):
    if not (request.user.is_superuser or request.user.role in FINANCE_STAFF_ROLES):
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.EXPORT,
            entity_type='FinancialExcelReport',
            outcome=AuditOutcome.DENIED,
            notes=f"Unauthorized financial export attempt by user {request.user.username}"
        )
        raise PermissionDenied("Access Denied: Financial Officer authorization required.")

    AuditLog.log_action(
        actor=request.user,
        action=AuditAction.EXPORT,
        entity_type='FinancialExcelReport',
        outcome=AuditOutcome.SUCCESS,
        notes="Generated and exported SACCO Financial Summary Excel"
    )
    excel_bytes = ReportExportService.generate_financial_excel()
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="NHT_Financial_Summary.xlsx"'
    return response
