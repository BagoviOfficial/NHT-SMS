from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views_auth, views_fleet, views_finance, views_ops

app_name = 'api'

router = DefaultRouter()
router.register(r'users', views_auth.UserManagementViewSet, basename='user')
router.register(r'staff', views_auth.StaffManagementViewSet, basename='staff')
router.register(r'members', views_fleet.MemberViewSet, basename='member')
router.register(r'vehicles', views_fleet.VehicleViewSet, basename='vehicle')
router.register(r'compliance-cards', views_fleet.VehicleComplianceCardViewSet, basename='compliance_card')
router.register(r'drivers', views_fleet.DriverViewSet, basename='driver')
router.register(r'driver-assignments', views_fleet.DriverAssignmentViewSet, basename='driver_assignment')
router.register(r'routes', views_fleet.RouteViewSet, basename='route')
router.register(r'route-assignments', views_fleet.VehicleRouteAssignmentViewSet, basename='route_assignment')
router.register(r'document-types', views_fleet.DocumentTypeViewSet, basename='document_type')
router.register(r'documents', views_fleet.DocumentViewSet, basename='document')
router.register(r'compliance-alerts', views_fleet.ComplianceAlertViewSet, basename='compliance_alert')
router.register(r'renewals', views_fleet.RenewalRequestViewSet, basename='renewal')
router.register(r'service-items', views_finance.ServiceItemViewSet, basename='service_item')
router.register(r'invoices', views_finance.InvoiceViewSet, basename='invoice')
router.register(r'payments', views_finance.PaymentViewSet, basename='payment')
router.register(r'receipts', views_finance.ReceiptViewSet, basename='receipt')
router.register(r'vouchers', views_finance.ManualPaymentVoucherViewSet, basename='voucher')
router.register(r'reconciliation-runs', views_finance.ReconciliationRunViewSet, basename='reconciliation_run')
router.register(r'reconciliation-exceptions', views_finance.ReconciliationExceptionViewSet, basename='reconciliation_exception')
router.register(r'accounts', views_finance.AccountViewSet, basename='account')
router.register(r'financial-periods', views_finance.FinancialPeriodViewSet, basename='financial_period')
router.register(r'journals', views_finance.JournalEntryViewSet, basename='journal')
router.register(r'expenses', views_finance.ExpenseViewSet, basename='expense')
router.register(r'maintenance-providers', views_ops.MaintenanceProviderViewSet, basename='maintenance_provider')
router.register(r'spare-parts', views_ops.SparePartViewSet, basename='spare_part')
router.register(r'maintenance', views_ops.MaintenanceRecordViewSet, basename='maintenance')
router.register(r'incidents', views_ops.IncidentViewSet, basename='incident')
router.register(r'committees', views_ops.CommitteeViewSet, basename='committee')
router.register(r'meetings', views_ops.MeetingViewSet, basename='meeting')
router.register(r'resolutions', views_ops.ResolutionViewSet, basename='resolution')
router.register(r'notifications', views_ops.NotificationViewSet, basename='notification')
router.register(r'notification-templates', views_ops.NotificationTemplateViewSet, basename='notification_template')
router.register(r'announcements', views_ops.AnnouncementViewSet, basename='announcement')
router.register(r'audit-logs', views_ops.AuditLogViewSet, basename='audit_log')

urlpatterns = [
    path('auth/me/', views_auth.AuthMeAPIView.as_view(), name='auth_me'),
    path('auth/login/', views_auth.AuthLoginAPIView.as_view(), name='auth_login'),
    path('auth/logout/', views_auth.AuthLogoutAPIView.as_view(), name='auth_logout'),
    path('auth/password-change/', views_auth.AuthPasswordChangeAPIView.as_view(), name='auth_password_change'),
    path('auth/mfa/setup/', views_auth.AuthMfaSetupAPIView.as_view(), name='auth_mfa_setup'),
    path('dashboard/', views_auth.DashboardAPIView.as_view(), name='dashboard'),
    path('superadmin/overview/', views_auth.SuperAdminOverviewAPIView.as_view(), name='superadmin_overview'),
    path('superadmin/clear-lockouts/', views_auth.SuperAdminClearLockoutsAPIView.as_view(), name='superadmin_clear_lockouts'),
    path('superadmin/terminate-sessions/', views_auth.SuperAdminTerminateSessionsAPIView.as_view(), name='superadmin_terminate_sessions'),
    path('superadmin/run-invoice-reminders/', views_auth.SuperAdminRunInvoiceRemindersAPIView.as_view(), name='superadmin_run_invoice_reminders'),
    path('driver/portal/', views_fleet.DriverPortalAPIView.as_view(), name='driver_portal'),
    path('compliance/scan/', views_fleet.ComplianceScanAPIView.as_view(), name='compliance_scan'),
    path('billing/statement/', views_finance.MemberStatementAPIView.as_view(), name='member_statement'),
    path('accounting/reports/', views_finance.FinancialReportsAPIView.as_view(), name='financial_reports'),
    path('notifications/preferences/', views_ops.CommunicationPreferenceAPIView.as_view(), name='comm_preferences'),
    path('reports/summary/', views_ops.ReportSummaryAPIView.as_view(), name='reports_summary'),
    path('', include(router.urls)),
]
