import base64
import io
import qrcode
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count, Q
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nht_sacco.apps.accounts.models import User, UserRole, STAFF_ROLES, LoginHistory
from nht_sacco.apps.accounts.permissions import (
    IsSystemAdmin,
    IsManagementStaff,
    MANAGEMENT_ROLES,
    is_super_admin,
)
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
from nht_sacco.apps.integrations.services import ConfigurationService
from nht_sacco.apps.reports.services import ExecutiveDashboardMetrics
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory
from .serializers import UserManagementSerializer, LoginHistorySerializer


ROLE_CAPABILITIES = {
    UserRole.SUPER_ADMIN: ['dashboard', 'members', 'vehicles', 'compliance-cards', 'drivers', 'routes', 'documents', 'compliance', 'renewals', 'billing', 'payments', 'reconciliation', 'accounting', 'maintenance', 'incidents', 'governance', 'notifications', 'reports', 'staff', 'users', 'settings', 'audit'],
    UserRole.CHAIRMAN: ['dashboard', 'members', 'vehicles', 'compliance-cards', 'drivers', 'routes', 'documents', 'compliance', 'renewals', 'billing', 'payments', 'reconciliation', 'accounting', 'maintenance', 'incidents', 'governance', 'notifications', 'reports', 'settings', 'audit'],
    UserRole.SECRETARY: ['dashboard', 'members', 'vehicles', 'compliance-cards', 'drivers', 'routes', 'documents', 'incidents', 'governance', 'notifications'],
    UserRole.FIELD_OFFICER: ['dashboard', 'members', 'vehicles', 'drivers', 'routes', 'maintenance', 'incidents'],
    UserRole.COMPLIANCE_OFFICER: ['dashboard', 'vehicles', 'compliance-cards', 'drivers', 'documents', 'compliance', 'renewals', 'maintenance', 'incidents', 'reports'],
    UserRole.RENEWAL_OFFICER: ['dashboard', 'vehicles', 'compliance-cards', 'documents', 'compliance', 'renewals'],
    UserRole.TREASURER: ['dashboard', 'members', 'billing', 'payments', 'reconciliation', 'accounting', 'reports'],
    UserRole.ACCOUNTANT: ['dashboard', 'members', 'billing', 'payments', 'reconciliation', 'accounting', 'reports'],
    UserRole.AUDITOR: ['dashboard', 'compliance', 'compliance-cards', 'accounting', 'reports', 'settings', 'audit'],
    UserRole.MEMBER: ['member-portal', 'notifications'],
    UserRole.DRIVER: ['driver-portal', 'notifications'],
}


def _active_branding_payload():
    from nht_sacco.apps.integrations.models import CompanyProfile
    profile = CompanyProfile.get_active()
    logo_url = '/settings/api/v1/company-profile/logo-asset/' if (profile.logo and profile.logo.name) else ''
    return {
        'sacco_name': profile.trading_name or ConfigurationService.get_str('business.sacco_name', 'Northern Highways Transporters SACCO'),
        'legal_name': profile.legal_name,
        'short_name': profile.short_name or 'NHT-SMS',
        'primary_color': profile.primary_color or ConfigurationService.get_str('app.brand_primary_color', '#10315C'),
        'secondary_color': profile.secondary_color or ConfigurationService.get_str('app.brand_secondary_color', '#FF8A00'),
        'currency': ConfigurationService.get_str('business.currency', 'KES'),
        'logo_url': logo_url,
        'branding_version': profile.current_version,
        'footer_text': profile.footer_text,
    }


def _build_me_payload(user, request=None):
    csrf_token = get_token(request) if request is not None else ''
    branding = _active_branding_payload()
    if not user or not user.is_authenticated:
        return {
            'authenticated': False,
            'csrf_token': csrf_token,
            'branding': branding,
        }

    role = UserRole.SUPER_ADMIN if user.is_superuser else user.role
    allowed_sections = ROLE_CAPABILITIES.get(role, ['member-portal'])
    has_totp = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
    member_id = str(user.member_profile.pk) if hasattr(user, 'member_profile') else None
    driver_id = str(user.driver_profile.pk) if hasattr(user, 'driver_profile') else None

    return {
        'authenticated': True,
        'csrf_token': csrf_token,
        'user': {
            'id': str(user.pk),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': user.get_full_name() or user.username,
            'phone_number': user.phone_number,
            'role': role,
            'role_display': user.get_role_display(),
            'is_superuser': user.is_superuser,
            'is_management_staff': user.is_management_staff,
            'is_member': user.is_member,
            'is_driver': getattr(user, 'is_driver', False),
            'must_change_password': user.must_change_password,
            'totp_enabled': has_totp,
            'member_id': member_id,
            'driver_id': driver_id,
            'default_route': allowed_sections[0] if allowed_sections else 'dashboard',
        },
        'allowed_sections': allowed_sections,
        'branding': branding,
    }


@method_decorator(ensure_csrf_cookie, name='dispatch')
class SpaIndexView(View):
    """
    Serves the CDN-based Material UI Single Page Application shell at /app/.
    """
    def get(self, request, *args, **kwargs):
        branding = _active_branding_payload()
        context = {
            'sacco_name': branding['sacco_name'],
            'primary_color': branding['primary_color'],
            'secondary_color': branding['secondary_color'],
            'currency': branding['currency'],
            'logo_url': branding['logo_url'],
        }
        return render(request, 'spa/index.html', context)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class AuthMeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(_build_me_payload(request.user, request=request), status=status.HTTP_200_OK)


class AuthLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request=request, username=username, password=password)
        if user is None:
            LoginHistory.objects.create(
                username_attempted=username,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                status=LoginHistory.Status.FAILED,
            )
            return Response({'error': 'Invalid credentials or account locked.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'error': 'Account is deactivated. Contact SACCO Admin.'}, status=status.HTTP_403_FORBIDDEN)

        login(request, user)
        LoginHistory.objects.create(
            user=user,
            username_attempted=username,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            status=LoginHistory.Status.SUCCESS,
        )
        return Response(_build_me_payload(user, request=request), status=status.HTTP_200_OK)


class AuthLogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.LOGOUT,
            entity_type='User',
            entity_id=str(request.user.pk),
            outcome=AuditOutcome.SUCCESS,
            notes='User logged out via SPA',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        logout(request)
        return Response({'success': True, 'csrf_token': get_token(request)}, status=status.HTTP_200_OK)


class AuthPasswordChangeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password') or ''
        new_password = request.data.get('new_password') or ''
        if not request.user.check_password(old_password):
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new_password, user=request.user)
        except DjangoValidationError as e:
            return Response({'error': ' '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.must_change_password = False
        request.user.save(update_fields=['password', 'must_change_password'])
        update_session_auth_hash(request, request.user)
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='UserPassword',
            entity_id=str(request.user.pk),
            outcome=AuditOutcome.SUCCESS,
            notes='Password updated via SPA',
        )
        return Response({'success': True, 'message': 'Password changed successfully.'})


class AuthMfaSetupAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
        if device:
            return Response({'enabled': True, 'device_name': device.name})

        unconfirmed, _ = TOTPDevice.objects.get_or_create(
            user=request.user,
            confirmed=False,
            defaults={'name': f"{request.user.username}-totp"}
        )
        qr_img = qrcode.make(unconfirmed.config_url)
        buf = io.BytesIO()
        qr_img.save(buf, format='PNG')
        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return Response({
            'enabled': False,
            'qr_data_url': f"data:image/png;base64,{qr_b64}",
            'otpauth_url': unconfirmed.config_url,
        })

    def post(self, request):
        token = (request.data.get('token') or '').strip()
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        if not device:
            return Response({'error': 'No pending TOTP device found.'}, status=status.HTTP_400_BAD_REQUEST)
        if not device.verify_token(token):
            return Response({'error': 'Invalid 6-digit authenticator code.'}, status=status.HTTP_400_BAD_REQUEST)
        device.confirmed = True
        device.save(update_fields=['confirmed'])
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='TOTPDevice',
            entity_id=str(device.pk),
            outcome=AuditOutcome.SUCCESS,
            notes='Enabled TOTP 2FA via SPA',
        )
        return Response({'enabled': True, 'message': 'Two-factor authentication activated.'})


def _other_active_super_admin_exists(exclude_pk):
    return User.objects.filter(is_active=True).filter(
        Q(role=UserRole.SUPER_ADMIN) | Q(is_superuser=True)
    ).exclude(pk=exclude_pk).exists()


class UserManagementViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin Staff & Role Management ViewSet.
    Strictly separates SACCO staff accounts from SACCO Member/Driver records,
    prevents privilege escalation to SUPER_ADMIN, and protects the last active Super Admin.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserManagementSerializer
    permission_classes = [IsSystemAdmin]
    filterset_fields = ['role', 'is_active', 'is_verified']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    staff_only = True

    def get_queryset(self):
        qs = super().get_queryset()
        scope = (self.request.query_params.get('scope') or '').lower()
        if self.staff_only and scope != 'all':
            return qs.filter(Q(role__in=STAFF_ROLES) | Q(is_superuser=True) | Q(is_staff=True))
        if scope == 'staff':
            return qs.filter(Q(role__in=STAFF_ROLES) | Q(is_superuser=True) | Q(is_staff=True))
        if scope == 'operational':
            return qs.filter(role__in=[UserRole.MEMBER, UserRole.DRIVER], is_superuser=False)
        return qs

    def perform_create(self, serializer):
        role = serializer.validated_data.get('role', UserRole.SECRETARY)
        if role == UserRole.SUPER_ADMIN and not is_super_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only an active Super Administrator may create a SUPER_ADMIN account.")
        user_obj = serializer.save()
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='StaffUser',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Provisioned user {user_obj.username} with role {user_obj.role}",
            ip_address=self.request.META.get('REMOTE_ADDR'),
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if (instance.role == UserRole.SUPER_ADMIN or instance.is_superuser) and not is_super_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only an active Super Administrator may modify a SUPER_ADMIN account.")
        user_obj = serializer.save()
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.UPDATE,
            entity_type='StaffUser',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Updated user profile for {user_obj.username}",
            ip_address=self.request.META.get('REMOTE_ADDR'),
        )

    def destroy(self, request, *args, **kwargs):
        user_obj = self.get_object()
        if user_obj.pk == request.user.pk:
            return Response({'error': 'You cannot delete your own active account.'}, status=status.HTTP_400_BAD_REQUEST)
        if (user_obj.role == UserRole.SUPER_ADMIN or user_obj.is_superuser) and not _other_active_super_admin_exists(user_obj.pk):
            return Response(
                {'error': 'Cannot delete the last active Super Administrator.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        username = user_obj.username
        res = super().destroy(request, *args, **kwargs)
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.DELETE,
            entity_type='StaffUser',
            entity_id=str(kwargs.get('pk', '')),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Removed staff account {username}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return res

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user_obj = self.get_object()
        new_role = request.data.get('role')
        if new_role not in UserRole.values:
            return Response({'error': f"Invalid role '{new_role}'."}, status=status.HTTP_400_BAD_REQUEST)

        actor_is_super = is_super_admin(request.user)
        if (new_role == UserRole.SUPER_ADMIN or user_obj.role == UserRole.SUPER_ADMIN or user_obj.is_superuser) and not actor_is_super:
            return Response(
                {'error': 'Only an active Super Administrator may assign or modify SUPER_ADMIN privileges.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        was_active_super = user_obj.is_active and (user_obj.role == UserRole.SUPER_ADMIN or user_obj.is_superuser)
        if was_active_super and new_role != UserRole.SUPER_ADMIN:
            if not _other_active_super_admin_exists(user_obj.pk):
                return Response(
                    {'error': 'Cannot demote the last active Super Administrator.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        old_role = user_obj.role
        user_obj.role = new_role
        if old_role == UserRole.SUPER_ADMIN and new_role != UserRole.SUPER_ADMIN:
            user_obj.is_superuser = False
        user_obj.save()
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='UserRole',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Changed role of {user_obj.username} from {old_role} to {new_role}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(UserManagementSerializer(user_obj).data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        user_obj = self.get_object()
        if user_obj.pk == request.user.pk:
            return Response({'error': 'You cannot deactivate your own active session.'}, status=status.HTTP_400_BAD_REQUEST)
        if user_obj.is_active and (user_obj.role == UserRole.SUPER_ADMIN or user_obj.is_superuser):
            if not _other_active_super_admin_exists(user_obj.pk):
                return Response(
                    {'error': 'Cannot deactivate the last active Super Administrator.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        user_obj.is_active = not user_obj.is_active
        user_obj.save(update_fields=['is_active'])
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='UserStatus',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"{'Activated' if user_obj.is_active else 'Deactivated'} account {user_obj.username}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(UserManagementSerializer(user_obj).data)

    @action(detail=True, methods=['post'])
    def initiate_recovery(self, request, pk=None):
        """
        Initiates staff account recovery: flags must_change_password and optionally
        dispatches a Django password reset email.
        """
        user_obj = self.get_object()
        send_email = bool(request.data.get('send_email', True))
        user_obj.must_change_password = True
        user_obj.save(update_fields=['must_change_password'])

        email_sent = False
        if send_email and user_obj.email:
            form = PasswordResetForm({'email': user_obj.email})
            if form.is_valid():
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name='accounts/password_reset_email.html' if False else 'registration/password_reset_email.html',
                )
                email_sent = True

        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='AccountRecovery',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Initiated account recovery for {user_obj.username} (email_sent={email_sent})",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response({
            'success': True,
            'must_change_password': True,
            'email_sent': email_sent,
            'message': f"Account recovery initiated for {user_obj.username}.",
        })

    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        user_obj = self.get_object()
        logins = LoginHistory.objects.filter(
            Q(user=user_obj) | Q(username_attempted=user_obj.username)
        ).order_by('-timestamp')[:25]
        audits = AuditLog.objects.filter(
            Q(actor=user_obj) | Q(entity_id=str(user_obj.pk))
        ).order_by('-timestamp')[:30]
        return Response({
            'login_history': LoginHistorySerializer(logins, many=True).data,
            'audit_logs': [
                {
                    'id': str(a.pk),
                    'actor': a.actor_username,
                    'action': a.action,
                    'entity_type': a.entity_type,
                    'entity_id': a.entity_id,
                    'outcome': a.outcome,
                    'notes': (a.change_details or {}).get('notes', ''),
                    'timestamp': a.timestamp.isoformat(),
                }
                for a in audits
            ],
        })

    @action(detail=False, methods=['get'])
    def roles(self, request):
        scope = (request.query_params.get('scope') or 'staff').lower()
        if scope == 'staff':
            choices = [{'value': r.value, 'label': str(r.label)} for r in UserRole if r in STAFF_ROLES]
            return Response(choices)
        return Response([{'value': k, 'label': str(v)} for k, v in UserRole.choices])

    @action(detail=False, methods=['get'])
    def login_history(self, request):
        logs = LoginHistory.objects.all().order_by('-timestamp')[:50]
        return Response(LoginHistorySerializer(logs, many=True).data)


class StaffManagementViewSet(UserManagementViewSet):
    """
    Dedicated Staff Management endpoint (/api/v1/staff/) strictly excluding
    SACCO Member and Driver operational accounts.
    """
    staff_only = True

    def get_queryset(self):
        return User.objects.filter(
            Q(role__in=STAFF_ROLES) | Q(is_superuser=True) | Q(is_staff=True)
        ).order_by('-date_joined')

    def perform_create(self, serializer):
        role = serializer.validated_data.get('role', UserRole.SECRETARY)
        if role not in STAFF_ROLES:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'role': 'Staff accounts cannot be created with Member or Driver operational roles.'})
        super().perform_create(serializer)

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        new_role = request.data.get('role')
        if new_role not in STAFF_ROLES:
            return Response(
                {'error': 'Staff Management only accepts SACCO staff roles; manage Members/Drivers in their dedicated registries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().assign_role(request, pk=pk)


class DashboardAPIView(APIView):
    permission_classes = [IsManagementStaff]

    def get(self, request):
        kpis = ExecutiveDashboardMetrics.get_kpis()
        category_map = dict(VehicleCategory.choices)
        fleet_categories = [
            {'category': str(category_map.get(c['category'], c['category'])), 'count': c['count']}
            for c in Vehicle.objects.values('category').annotate(count=Count('id')).order_by('-count')
        ]
        recent_audit = [
            {
                'id': str(l.pk),
                'actor': l.actor_username or 'SYSTEM',
                'action': l.action,
                'entity_type': l.entity_type,
                'entity_id': l.entity_id,
                'outcome': l.outcome,
                'timestamp': l.timestamp.isoformat(),
            }
            for l in AuditLog.objects.all().order_by('-timestamp')[:10]
        ]

        # Hide exact financial totals from non-finance/non-oversight operational staff
        can_see_finance = request.user.is_superuser or request.user.role in {
            UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.TREASURER, UserRole.ACCOUNTANT, UserRole.AUDITOR
        }
        financials = {
            'total_invoiced': str(kpis['total_invoiced']) if can_see_finance else None,
            'total_collected': str(kpis['total_collected']) if can_see_finance else None,
            'total_outstanding': str(kpis['total_outstanding']) if can_see_finance else None,
            'total_expenses': str(kpis['total_expenses']) if can_see_finance else None,
            'net_cash': str(kpis['net_cash']) if can_see_finance else None,
            'restricted': not can_see_finance,
        }

        recent_transactions = []
        if can_see_finance:
            from nht_sacco.apps.payments.models import Payment, PaymentStatus
            for p in Payment.objects.filter(status=PaymentStatus.SUCCESS).select_related('member', 'invoice').order_by('-confirmed_at', '-created_at')[:8]:
                recent_transactions.append({
                    'id': str(p.pk),
                    'reference': p.provider_transaction_id or p.payment_reference,
                    'member_name': p.member.full_name if p.member else 'N/A',
                    'invoice_number': p.invoice.invoice_number if p.invoice else 'N/A',
                    'method': p.get_method_display(),
                    'amount': str(p.amount),
                    'confirmed_at': (p.confirmed_at or p.created_at).isoformat(),
                })

        return Response({
            'kpis': {
                'total_members': kpis['total_members'],
                'active_members': kpis['active_members'],
                'pending_members': kpis['pending_members'],
                'suspended_members': kpis.get('suspended_members', 0),
                'total_vehicles': kpis['total_vehicles'],
                'active_vehicles': kpis.get('active_vehicles', 0),
                'vehicles_awaiting_compliance': kpis.get('vehicles_awaiting_compliance', 0),
                'compliant_vehicles': kpis['compliant_vehicles'],
                'delinquent_vehicles': kpis['delinquent_vehicles'],
                'compliance_rate': kpis['compliance_rate'],
                'expiring_docs': kpis['expiring_docs'],
                'expired_docs': kpis['expired_docs'],
                'expiring_certificates': kpis.get('expiring_certificates', 0),
                'expired_certificates': kpis.get('expired_certificates', 0),
                'active_routes': kpis.get('active_routes', 0),
                'system_alerts': kpis.get('system_alerts', 0),
                'pending_approvals': kpis.get('pending_approvals', 0),
                'financials': financials,
                'route_distribution': kpis['route_distribution'],
            },
            'fleet_categories': fleet_categories,
            'recent_transactions': recent_transactions,
            'recent_audit': recent_audit,
        })
