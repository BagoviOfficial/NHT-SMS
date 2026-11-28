"""
Centralized DRF Role-Based Access Control (RBAC) & Anti-IDOR permission classes
for NHT-SMS spanning all 11 operational and self-service personas.
"""

from django.db.models import Q
from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import STAFF_ROLES, UserRole


MANAGEMENT_ROLES = set(STAFF_ROLES)

REGISTRY_OPS_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHAIRMAN,
    UserRole.SECRETARY,
    UserRole.FIELD_OFFICER,
}

FINANCE_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.TREASURER,
    UserRole.ACCOUNTANT,
}

FINANCE_CHECKER_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.CHAIRMAN,
    UserRole.TREASURER,
    UserRole.ACCOUNTANT,
}

COMPLIANCE_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.CHAIRMAN,
}

RENEWAL_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.RENEWAL_OFFICER,
    UserRole.CHAIRMAN,
}


def is_super_admin(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or getattr(user, 'role', None) == UserRole.SUPER_ADMIN)
    )


def has_any_role(user, roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', None) == UserRole.SUPER_ADMIN:
        return True
    return getattr(user, 'role', None) in roles


class IsSystemAdmin(BasePermission):
    message = "Super Administrator clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, {UserRole.SUPER_ADMIN})


class IsManagementStaff(BasePermission):
    message = "SACCO management staff clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, MANAGEMENT_ROLES)


class IsRegistryOrOpsStaff(BasePermission):
    message = "Registry or Operations staff clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, REGISTRY_OPS_ROLES)


class IsFinanceStaff(BasePermission):
    message = "SACCO Finance staff (Treasurer / Accountant) clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, FINANCE_STAFF_ROLES)


class IsFinanceChecker(BasePermission):
    message = "Finance Checker clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, FINANCE_CHECKER_ROLES)


class IsComplianceStaff(BasePermission):
    message = "Compliance Officer clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, COMPLIANCE_STAFF_ROLES)


class IsRenewalStaff(BasePermission):
    message = "Renewal Officer clearance required."

    def has_permission(self, request, view):
        return has_any_role(request.user, RENEWAL_STAFF_ROLES)


class IsAuditorReadOnly(BasePermission):
    """
    Allows Auditor read-only (SAFE_METHODS) access; blocks mutations.
    """
    message = "Auditors hold strict read-only inspection privileges."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser or request.user.role == UserRole.SUPER_ADMIN:
            return True
        return request.user.role == UserRole.AUDITOR and request.method in SAFE_METHODS


class IsMemberUser(BasePermission):
    message = "Active SACCO Member profile required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == UserRole.MEMBER or hasattr(request.user, 'member_profile'))
        )


class IsDriverUser(BasePermission):
    message = "Active Commercial Fleet Driver profile required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == UserRole.DRIVER or hasattr(request.user, 'driver_profile'))
        )


def role_permission_factory(allowed_write_roles, allow_auditor_read=False):
    """
    Builds a DRF permission class allowing `allowed_write_roles` full access
    and optionally granting `AUDITOR` (or any read roles) SAFE_METHODS read access.
    """
    allowed_set = set(allowed_write_roles)

    class RoleScopedPermission(BasePermission):
        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
                return True
            if user.role in allowed_set:
                return True
            if allow_auditor_read and user.role == UserRole.AUDITOR and request.method in SAFE_METHODS:
                return True
            return False

    return RoleScopedPermission


def scope_queryset_for_member(qs, user, lookup='member', q_builder=None):
    """
    Restricts a queryset to records belonging to `user.member_profile` when
    the caller holds the MEMBER role, returning `qs.none()` if unlinked.
    """
    if getattr(user, 'role', None) != UserRole.MEMBER:
        return qs
    member = getattr(user, 'member_profile', None)
    if not member:
        return qs.none()
    if q_builder is not None:
        return qs.filter(q_builder(member))
    return qs.filter(**{lookup: member})
