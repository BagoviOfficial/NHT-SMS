import time
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout
from django.contrib import messages


class SessionSecurityMiddleware:
    """
    Middleware enforcing session security policies:
    1. Mandatory Password Change: Users with must_change_password=True are restricted
       exclusively to the password change and logout endpoints.
    2. Idle Session Expiration: Enforces role-based session inactivity timeouts:
       - Staff & Management: 30 minutes (configurable via SESSION_IDLE_TIMEOUT_STAFF_SECONDS)
       - Ordinary Members: 12 hours (configurable via SESSION_IDLE_TIMEOUT_MEMBER_SECONDS)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # 1. Check Idle Session Expiration
            now = time.time()
            last_activity = request.session.get('last_activity')
            
            is_staff = request.user.is_staff or getattr(request.user, 'is_management_staff', False)
            if is_staff:
                timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT_STAFF_SECONDS', 1800)  # 30 minutes
            else:
                timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT_MEMBER_SECONDS', 43200) # 12 hours

            if last_activity and (now - last_activity) > timeout:
                logout(request)
                messages.warning(request, "Your session has expired due to inactivity. Please log in again.")
                return redirect('accounts:login')

            request.session['last_activity'] = now

            # 2. Check Forced Password Change
            if getattr(request.user, 'must_change_password', False):
                try:
                    pw_change_url = reverse('accounts:password_change')
                    logout_url = reverse('accounts:logout')
                except Exception:
                    pw_change_url = '/accounts/password-change/'
                    logout_url = '/accounts/logout/'

                static_url = getattr(settings, 'STATIC_URL', '/static/')
                media_url = getattr(settings, 'MEDIA_URL', '/media/')

                # Allow password change, logout, static, and media assets
                path = request.path
                allowed = (
                    path.startswith(pw_change_url) or
                    path.startswith(logout_url) or
                    path.startswith('/api/v1/auth/password-change/') or
                    path.startswith('/api/v1/auth/logout/') or
                    path.startswith('/api/v1/auth/me/') or
                    path.startswith(static_url) or
                    path.startswith(media_url)
                )

                if not allowed:
                    messages.warning(request, "Security Policy: You must change your password before continuing.")
                    return redirect('accounts:password_change')

        response = self.get_response(request)
        return response
