from rest_framework import permissions
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from nht_sacco.apps.accounts.models import UserRole


class IsSystemAdminUser(permissions.BasePermission):
    """
    Allows write and management access only to Super Administrators.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            request.user.is_superuser
            or getattr(request.user, 'role', None) == UserRole.SUPER_ADMIN
        )


class IsAuditorOrSystemAdmin(permissions.BasePermission):
    """
    Grants read-only access to Auditors and Super Administrators.
    Mutating methods require Super Administrator privileges.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        is_super = request.user.is_superuser or getattr(request.user, 'role', None) == UserRole.SUPER_ADMIN
        if is_super:
            return True

        if request.method in permissions.SAFE_METHODS:
            return getattr(request.user, 'role', None) in [UserRole.AUDITOR, UserRole.CHAIRMAN]

        return False


class SystemAdminRequiredMixin(UserPassesTestMixin):
    """
    Django CBV access control: restricted to Super Administrators.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or getattr(user, 'role', None) == UserRole.SUPER_ADMIN
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Access Denied: Only authorized System Administrators can modify configurations.")
        return super().handle_no_permission()


class AuditorOrAdminRequiredMixin(UserPassesTestMixin):
    """
    Django CBV access control: allows view access to Auditors and Administrators.
    """
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser
            or getattr(user, 'role', None) in [UserRole.SUPER_ADMIN, UserRole.AUDITOR, UserRole.CHAIRMAN]
        )

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("Access Denied: You do not possess clearance to inspect system configuration.")
        return super().handle_no_permission()
