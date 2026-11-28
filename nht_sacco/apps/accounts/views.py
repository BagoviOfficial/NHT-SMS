from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django_otp.plugins.otp_totp.models import TOTPDevice
import django_otp

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.config.mui import MUI_TEMPLATE_NAME, get_mui_context, render_mui_app
from .models import UserRole
from .services import AccountSecurityService


class MuiTemplateContextMixin:
    """
    Supplies the single MUI SPA shell (`templates/spa/index.html`) context
    to Django generic auth views without duplicating HTML templates.
    """
    template_name = MUI_TEMPLATE_NAME
    mui_route = ''
    mui_title = ''

    def get_mui_page_data(self):
        return {}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            get_mui_context(
                self.request,
                initial_route=self.mui_route,
                page_title=self.mui_title,
                page_data=self.get_mui_page_data(),
            )
        )
        return ctx


class CustomLoginView(MuiTemplateContextMixin, LoginView):
    mui_route = 'login'
    mui_title = 'Sign In'
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if getattr(user, 'must_change_password', False):
            return reverse_lazy('accounts:password_change')
        if user.is_member or (hasattr(user, 'member_profile') and not user.is_management_staff):
            return reverse_lazy('portal:dashboard')
        if getattr(user, 'is_driver', False) or (hasattr(user, 'driver_profile') and not user.is_management_staff):
            return '/app/#driver-portal'
        if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
            return '/admin/'
        if user.is_staff or user.is_management_staff:
            return reverse_lazy('accounts:dashboard')
        return reverse_lazy('accounts:profile')


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')

    def dispatch(self, request, *args, **kwargs):
        messages.info(request, "You have been logged out securely.")
        return super().dispatch(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        logins = [
            {
                'timestamp': r.timestamp.isoformat(),
                'status': r.status,
                'ip_address': r.ip_address or '-',
                'user_agent': (r.user_agent or '')[:60],
            }
            for r in user.login_records.all()[:5]
        ]
        return render_mui_app(
            request,
            initial_route='profile',
            page_title='User Profile & Security',
            page_data={
                'profile': {
                    'username': user.username,
                    'full_name': user.get_full_name() or 'Not specified',
                    'email': user.email,
                    'phone_number': user.phone_number or 'Not registered',
                    'national_id': user.national_id or 'Not registered',
                    'role': user.role,
                    'role_display': user.get_role_display(),
                    'is_active': user.is_active,
                    'last_login_ip': user.last_login_ip or 'None recorded',
                    'date_joined': user.date_joined.isoformat() if user.date_joined else '',
                    'recent_logins': logins,
                }
            },
        )


class DashboardView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.is_member or (hasattr(request.user, 'member_profile') and not request.user.is_management_staff):
            return redirect('portal:dashboard')
        if getattr(request.user, 'is_driver', False) or (hasattr(request.user, 'driver_profile') and not request.user.is_management_staff):
            return redirect('/app/#driver-portal')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return render_mui_app(
            request,
            initial_route='dashboard',
            page_title='SACCO Operations Dashboard',
        )


class CustomPasswordChangeView(LoginRequiredMixin, MuiTemplateContextMixin, PasswordChangeView):
    mui_route = 'password-change'
    mui_title = 'Change Password'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        response = super().form_valid(form)
        AccountSecurityService.finalize_password_change(
            user=self.request.user,
            current_session_key=self.request.session.session_key,
            ip_address=self.request.META.get('REMOTE_ADDR'),
        )
        messages.success(self.request, "Your password was updated successfully.")
        return response


class LockoutView(View):
    def get(self, request, *args, **kwargs):
        return render_mui_app(
            request,
            initial_route='lockout',
            page_title='Account Temporarily Locked',
        )


# ==============================================================================
# Multi-Factor Authentication (MFA / TOTP) Views
# ==============================================================================

class TOTPSetupView(LoginRequiredMixin, View):
    """
    Enables user enrollment in Time-based One-Time Password (TOTP) MFA.
    """
    def get(self, request, *args, **kwargs):
        user = request.user
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if not device:
            device = TOTPDevice.objects.create(user=user, name=f"{user.username}-totp", confirmed=False)

        return JsonResponse({
            'status': 'success',
            'username': user.username,
            'config_url': device.config_url,
            'secret_key': device.key,
            'message': 'Scan the QR code or enter the secret key into your authenticator app, then verify with a 6-digit code.',
        })

    def post(self, request, *args, **kwargs):
        user = request.user
        token = request.POST.get('token', '').strip()
        if not token:
            return JsonResponse({'status': 'error', 'message': 'Missing verification token.'}, status=400)

        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if not device:
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
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            return JsonResponse({'status': 'success', 'message': 'TOTP multi-factor authentication enrolled successfully.'})
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid verification code. Please check your authenticator clock and try again.'},
            status=400,
        )


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

        AuditLog.log_action(
            actor=user,
            action=AuditAction.SYSTEM,
            entity_type='SECURITY_MFA',
            entity_id=user.username,
            outcome=AuditOutcome.DENIED,
            notes="Failed TOTP multi-factor authentication token challenge.",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return JsonResponse({'status': 'error', 'message': 'Invalid verification token.'}, status=401)


# ==============================================================================
# Secure Password Reset Views (Anti-User-Enumeration)
# ==============================================================================

class CustomPasswordResetView(MuiTemplateContextMixin, PasswordResetView):
    mui_route = 'password-reset'
    mui_title = 'Reset Password'
    email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        AuditLog.log_action(
            actor=None,
            action=AuditAction.SYSTEM,
            entity_type='SECURITY_RESET',
            entity_id=form.cleaned_data.get('email', 'unknown'),
            outcome=AuditOutcome.SUCCESS,
            notes="Password reset requested.",
            ip_address=self.request.META.get('REMOTE_ADDR'),
        )
        return super().form_valid(form)


class CustomPasswordResetDoneView(MuiTemplateContextMixin, PasswordResetDoneView):
    mui_route = 'password-reset-done'
    mui_title = 'Password Reset Sent'


class CustomPasswordResetConfirmView(MuiTemplateContextMixin, PasswordResetConfirmView):
    mui_route = 'password-reset-confirm'
    mui_title = 'Set New Password'
    success_url = reverse_lazy('accounts:password_reset_complete')

    def get_mui_page_data(self):
        return {'validlink': bool(getattr(self, 'validlink', False))}


class CustomPasswordResetCompleteView(MuiTemplateContextMixin, PasswordResetCompleteView):
    mui_route = 'password-reset-complete'
    mui_title = 'Password Reset Complete'
