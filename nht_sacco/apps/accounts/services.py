"""
Shared account security services (session termination, password change finalization).
"""

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db.models import Q
from django.utils import timezone

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome


class AccountSecurityService:
    @staticmethod
    def other_active_super_admin_exists(exclude_pk) -> bool:
        """
        Returns True if another active Super Admin (by role or is_superuser)
        exists besides `exclude_pk`. Protects against removing the last Super Admin.
        """
        from .models import UserRole
        User = get_user_model()
        return (
            User.objects.filter(is_active=True)
            .filter(Q(role=UserRole.SUPER_ADMIN) | Q(is_superuser=True))
            .exclude(pk=exclude_pk)
            .exists()
        )
    @staticmethod
    def terminate_sessions(*, target_user_id=None, exclude_session_key=None) -> int:
        """
        Terminates active database sessions, optionally filtered to a single user
        and/or excluding the caller's current session key.
        """
        terminated = 0
        for sess in Session.objects.filter(expire_date__gte=timezone.now()):
            if exclude_session_key and sess.session_key == exclude_session_key:
                continue
            if target_user_id is not None:
                try:
                    data = sess.get_decoded()
                    if str(data.get('_auth_user_id', '')) != str(target_user_id):
                        continue
                except Exception:
                    continue
            sess.delete()
            terminated += 1
        return terminated

    @classmethod
    def finalize_password_change(
        cls,
        *,
        user,
        current_session_key=None,
        ip_address=None,
        notes='User password updated; external concurrent sessions terminated.',
    ) -> int:
        """
        Clears forced password change flag, terminates all other active sessions
        for the user, and records an immutable security audit entry.
        """
        if getattr(user, 'must_change_password', False):
            user.must_change_password = False
            user.save(update_fields=['must_change_password'])

        terminated = cls.terminate_sessions(
            target_user_id=user.pk,
            exclude_session_key=current_session_key,
        )

        AuditLog.log_action(
            actor=user,
            action=AuditAction.SYSTEM,
            entity_type='SECURITY_CREDENTIAL',
            entity_id=user.username,
            outcome=AuditOutcome.SUCCESS,
            notes=notes,
            ip_address=ip_address,
        )
        return terminated
