import base64
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

from django_otp.plugins.otp_totp.models import TOTPDevice
import django_otp

from .forms import CustomAuthenticationForm, CustomPasswordChangeForm
from .models import UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
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
        if getattr(user, 'must_change_password', False):
            return reverse_lazy('accounts:password_change')
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
