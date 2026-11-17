from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from .forms import CustomAuthenticationForm, CustomPasswordChangeForm
from .models import UserRole
from nht_sacco.apps.audit.models import AuditLog
from nht_sacco.apps.members.models import Member, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_staff or user.is_management_staff:
            return reverse_lazy('accounts:dashboard')
        return reverse_lazy('accounts:profile')

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, "You have been logged out securely.")
        return super().dispatch(request, *args, **kwargs)

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'admin/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'SACCO Management Dashboard'
        ctx['total_members'] = Member.objects.filter(status=MembershipStatus.ACTIVE).count()
        
        active_vehicles = Vehicle.objects.filter(status=VehicleStatus.ACTIVE)
        ctx['total_vehicles'] = active_vehicles.count()

        if active_vehicles.exists():
            compliant_count = sum(1 for v in active_vehicles if ComplianceService.get_vehicle_compliance_status(v)['status'] == ComplianceStatus.FULLY_COMPLIANT)
            ctx['compliance_rate'] = round((compliant_count / active_vehicles.count()) * 100)
        else:
            ctx['compliance_rate'] = 100

        unpaid_invoices = Invoice.objects.exclude(status__in=[InvoiceStatus.PAID, InvoiceStatus.CANCELLED])
        ctx['pending_revenue'] = f"{sum(inv.balance_due for inv in unpaid_invoices):,.2f}"

        ctx['recent_logs'] = AuditLog.objects.all().order_by('-timestamp')[:10]
        return ctx

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, "Your password was updated successfully.")
        return super().form_valid(form)

class LockoutView(TemplateView):
    template_name = 'accounts/lockout.html'
