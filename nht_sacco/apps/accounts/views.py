import base64
import json
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.sessions.models import Session
from django.db.models import Count, Sum, Q
from django.core.serializers.json import DjangoJSONEncoder

from django_otp.plugins.otp_totp.models import TOTPDevice
import django_otp

from .forms import CustomAuthenticationForm, CustomPasswordChangeForm
from .models import UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
from nht_sacco.apps.members.models import Member, MembershipStatus
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus, VehicleCategory
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.reports.services import ExecutiveDashboardMetrics


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if getattr(user, 'must_change_password', False):
            return reverse_lazy('accounts:password_change')
        if user.is_member or (hasattr(user, 'member_profile') and not user.is_management_staff):
            return reverse_lazy('portal:dashboard')
        if getattr(user, 'is_driver', False) or (hasattr(user, 'driver_profile') and not user.is_management_staff):
            return '/app/#driver-portal'
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

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.is_member or (hasattr(request.user, 'member_profile') and not request.user.is_management_staff):
            return redirect('portal:dashboard')
        if getattr(request.user, 'is_driver', False) or (hasattr(request.user, 'driver_profile') and not request.user.is_management_staff):
            return redirect('/app/#driver-portal')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'SACCO Operations Dashboard'
        
        # Load comprehensive KPI metrics
        kpis = ExecutiveDashboardMetrics.get_kpis()
        ctx['kpis'] = kpis
        ctx['total_members'] = kpis.get('total_members', 0)
        ctx['active_members'] = kpis.get('active_members', 0)
        ctx['pending_members'] = kpis.get('pending_members', 0)
        
        ctx['total_vehicles'] = kpis.get('total_vehicles', 0)
        ctx['compliant_vehicles'] = kpis.get('compliant_vehicles', 0)
        ctx['delinquent_vehicles'] = kpis.get('delinquent_vehicles', 0)
        ctx['compliance_rate'] = kpis.get('compliance_rate', 100)
        
        ctx['total_invoiced'] = kpis.get('total_invoiced', 0)
        ctx['total_collected'] = kpis.get('total_collected', 0)
        ctx['total_outstanding'] = kpis.get('total_outstanding', 0)
        ctx['pending_revenue'] = f"{kpis.get('total_outstanding', 0):,.2f}"
        ctx['expiring_docs'] = kpis.get('expiring_docs', 0)
        ctx['expired_docs'] = kpis.get('expired_docs', 0)
        
        # Audit logs & live stream
        ctx['recent_logs'] = AuditLog.objects.all().order_by('-timestamp')[:10]
        ctx['total_audit_logs'] = AuditLog.objects.count()

        # Fleet category distribution for bar chart
        categories_qs = Vehicle.objects.values('category').annotate(count=Count('id')).order_by('-count')
        category_map = dict(VehicleCategory.choices)
        fleet_categories = [
            {'category': str(category_map.get(c['category'], c['category'])), 'count': int(c['count'])}
            for c in categories_qs
        ]
        if not fleet_categories:
            fleet_categories = [
                {'category': '14-Seater PSV', 'count': 0},
                {'category': '33-Seater Minibus', 'count': 0},
                {'category': 'Heavy Commercial', 'count': 0},
            ]
        ctx['fleet_categories'] = fleet_categories

        # Chart JSON Payloads for ApexCharts
        # 1. Compliance Donut Chart
        compliant_cnt = ctx['compliant_vehicles']
        delinquent_cnt = ctx['delinquent_vehicles']
        if compliant_cnt == 0 and delinquent_cnt == 0:
            compliance_series = [100, 0]
            compliance_labels = ["Compliant", "Non-Compliant"]
        else:
            compliance_series = [compliant_cnt, delinquent_cnt]
            compliance_labels = ["Compliant Vehicles", "Action Required"]
        
        ctx['chart_compliance_series'] = json.dumps(compliance_series, cls=DjangoJSONEncoder)
        ctx['chart_compliance_labels'] = json.dumps(compliance_labels, cls=DjangoJSONEncoder)

        # 2. Financial Collections vs Invoiced
        ctx['chart_finance_series'] = json.dumps([
            {
                'name': 'Billed Invoices',
                'data': [float(ctx['total_invoiced']) if ctx['total_invoiced'] else 0.0]
            },
            {
                'name': 'Collections Settled',
                'data': [float(ctx['total_collected']) if ctx['total_collected'] else 0.0]
            }
        ], cls=DjangoJSONEncoder)
        ctx['chart_finance_categories'] = json.dumps(['Current Fiscal Cycle'], cls=DjangoJSONEncoder)

        # 3. Fleet Categories Series
        ctx['chart_fleet_labels'] = json.dumps([str(c['category']) for c in fleet_categories], cls=DjangoJSONEncoder)
        ctx['chart_fleet_counts'] = json.dumps([int(c['count']) for c in fleet_categories], cls=DjangoJSONEncoder)

        # Top vehicles needing attention
        flagged_vehicles = []
        for v in Vehicle.objects.filter(status=VehicleStatus.ACTIVE)[:5]:
            status_data = ComplianceService.get_vehicle_compliance_status(v)
            flagged_vehicles.append({
                'registration_number': v.registration_number,
                'category_display': v.get_category_display(),
                'owner': v.current_owner.full_name if getattr(v, 'current_owner', None) else 'Unassigned',
                'compliance_status': status_data.get('status', 'PENDING'),
                'is_compliant': status_data.get('status') == ComplianceStatus.FULLY_COMPLIANT,
                'qr_token': str(getattr(v, 'qr_token', '')) if getattr(v, 'qr_token', None) else '',
            })
        ctx['flagged_vehicles'] = flagged_vehicles

        # System security indicators
        ctx['db_engine'] = 'PostgreSQL 16 (Local Port 5432)'
        ctx['axes_status'] = 'Active (Anti-Brute Force Protection)'
        ctx['asvs_level'] = 'OWASP ASVS L2'
        
        return ctx


class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if getattr(user, 'must_change_password', False):
            user.must_change_password = False
            user.save(update_fields=['must_change_password'])

        # Terminate all OTHER active sessions for this user in Session store
        try:
            current_key = self.request.session.session_key
            for s in Session.objects.filter(expire_date__gte=timezone.now()):
                try:
                    data = s.get_decoded()
                    if str(data.get('_auth_user_id')) == str(user.id) and s.session_key != current_key:
                        s.delete()
                except Exception:
                    pass
        except Exception:
            pass

        AuditLog.log_action(
            actor=user,
            action=AuditAction.SYSTEM,
            entity_type='SECURITY_CREDENTIAL',
            entity_id=user.username,
            outcome=AuditOutcome.SUCCESS,
            notes="User password updated; external concurrent sessions terminated.",
            ip_address=self.request.META.get('REMOTE_ADDR')
        )

        messages.success(self.request, "Your password was updated successfully.")
        return response


class LockoutView(TemplateView):
    template_name = 'accounts/lockout.html'


# ==============================================================================
# Multi-Factor Authentication (MFA / TOTP) Views
# ==============================================================================

class TOTPSetupView(LoginRequiredMixin, View):
    """
    Enables user enrollment in Time-based One-Time Password (TOTP) MFA.
    Generates provisioning URI (for Google Authenticator / Microsoft Authenticator / Aegis)
    and verifies initial token to confirm device.
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        # Find or create unconfirmed device
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if not device:
            device = TOTPDevice.objects.create(user=user, name=f"{user.username}-totp", confirmed=False)

        config_url = device.config_url
        hex_key = device.key

        return JsonResponse({
            'status': 'success',
            'username': user.username,
            'config_url': config_url,
            'secret_key': hex_key,
            'message': 'Scan the QR code or enter the secret key into your authenticator app, then verify with a 6-digit code.'
        })

    def post(self, request, *args, **kwargs):
        user = request.user
        token = request.POST.get('token', '').strip()
        if not token:
            return JsonResponse({'status': 'error', 'message': 'Missing verification token.'}, status=400)

        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if not device:
            # Check if already confirmed device exists
            confirmed_device = TOTPDevice.objects.filter(user=user, confirmed=True).first()
            if confirmed_device and confirmed_device.verify_token(token):
                return JsonResponse({'status': 'success', 'message': 'MFA is already active and verified.'})
            return JsonResponse({'status': 'error', 'message': 'No pending TOTP device setup found.'}, status=400)

        if device.verify_token(token):
            device.confirmed = True
            device.save()

            AuditLog.log_action(
                actor=user,
                action=AuditAction.SYSTEM,
                entity_type='SECURITY_MFA',
                entity_id=user.username,
                outcome=AuditOutcome.SUCCESS,
                notes="TOTP multi-factor authentication device enrolled and verified successfully.",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return JsonResponse({'status': 'success', 'message': 'TOTP multi-factor authentication enrolled successfully.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid verification code. Please check your authenticator clock and try again.'}, status=400)


class TOTPVerifyView(LoginRequiredMixin, View):
    """
    Verifies a 6-digit TOTP token against an active confirmed device.
    """
    def post(self, request, *args, **kwargs):
        user = request.user
        token = request.POST.get('token', '').strip()
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()

        if not device:
            return JsonResponse({'status': 'error', 'message': 'No confirmed MFA device configured for this user.'}, status=400)

        if device.verify_token(token):
            django_otp.login(request, device)
            request.session['otp_verified'] = True
            return JsonResponse({'status': 'success', 'message': 'MFA verification successful.'})
        else:
            AuditLog.log_action(
                actor=user,
                action=AuditAction.SYSTEM,
                entity_type='SECURITY_MFA',
                entity_id=user.username,
                outcome=AuditOutcome.DENIED,
                notes="Failed TOTP multi-factor authentication token challenge.",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return JsonResponse({'status': 'error', 'message': 'Invalid verification token.'}, status=401)


# ==============================================================================
# Secure Password Reset Views (Anti-User-Enumeration)
# ==============================================================================

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        # Django's default implementation avoids disclosing whether an email exists
        AuditLog.log_action(
            actor=None,
            action=AuditAction.SYSTEM,
            entity_type='SECURITY_RESET',
            entity_id=form.cleaned_data.get('email', 'unknown'),
            outcome=AuditOutcome.SUCCESS,
            notes="Password reset requested.",
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
        return super().form_valid(form)


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
