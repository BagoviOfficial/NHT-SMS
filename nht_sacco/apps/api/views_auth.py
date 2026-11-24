import base64
import io
import qrcode
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
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

from nht_sacco.apps.accounts.models import User, UserRole, LoginHistory
from nht_sacco.apps.accounts.permissions import (
    IsSystemAdmin,
    IsManagementStaff,
    MANAGEMENT_ROLES,
)
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
from nht_sacco.apps.integrations.services import ConfigurationService
from nht_sacco.apps.reports.services import ExecutiveDashboardMetrics
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory
from .serializers import UserManagementSerializer, LoginHistorySerializer


ROLE_CAPABILITIES = {
    UserRole.SUPER_ADMIN: ['dashboard', 'members', 'vehicles', 'drivers', 'routes', 'documents', 'compliance', 'renewals', 'billing', 'payments', 'reconciliation', 'accounting', 'maintenance', 'incidents', 'governance', 'notifications', 'reports', 'users', 'settings', 'audit'],
    UserRole.CHAIRMAN: ['dashboard', 'members', 'vehicles', 'drivers', 'routes', 'documents', 'compliance', 'renewals', 'billing', 'payments', 'reconciliation', 'accounting', 'maintenance', 'incidents', 'governance', 'notifications', 'reports', 'settings', 'audit'],
    UserRole.SECRETARY: ['dashboard', 'members', 'vehicles', 'drivers', 'routes', 'documents', 'incidents', 'governance', 'notifications'],
    UserRole.FIELD_OFFICER: ['dashboard', 'members', 'vehicles', 'drivers', 'routes', 'maintenance', 'incidents'],
    UserRole.COMPLIANCE_OFFICER: ['dashboard', 'vehicles', 'drivers', 'documents', 'compliance', 'renewals', 'maintenance', 'incidents', 'reports'],
    UserRole.RENEWAL_OFFICER: ['dashboard', 'vehicles', 'documents', 'compliance', 'renewals'],
    UserRole.TREASURER: ['dashboard', 'members', 'billing', 'payments', 'reconciliation', 'accounting', 'reports'],
    UserRole.ACCOUNTANT: ['dashboard', 'members', 'billing', 'payments', 'reconciliation', 'accounting', 'reports'],
    UserRole.AUDITOR: ['dashboard', 'compliance', 'accounting', 'reports', 'settings', 'audit'],
    UserRole.MEMBER: ['member-portal', 'notifications'],
    UserRole.DRIVER: ['driver-portal', 'notifications'],
}


def _build_me_payload(user, request=None):
    csrf_token = get_token(request) if request is not None else ''
    if not user or not user.is_authenticated:
        return {
            'authenticated': False,
            'csrf_token': csrf_token,
            'branding': {
                'sacco_name': ConfigurationService.get_str('business.sacco_name', 'Northern Highways Transporters SACCO'),
                'short_name': 'NHT-SMS',
                'primary_color': ConfigurationService.get_str('app.brand_primary_color', '#10315C'),
                'secondary_color': ConfigurationService.get_str('app.brand_secondary_color', '#FF8A00'),
                'currency': ConfigurationService.get_str('business.currency', 'KES'),
            },
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
        'branding': {
            'sacco_name': ConfigurationService.get_str('business.sacco_name', 'Northern Highways Transporters SACCO'),
            'short_name': 'NHT-SMS',
            'primary_color': ConfigurationService.get_str('app.brand_primary_color', '#10315C'),
            'secondary_color': ConfigurationService.get_str('app.brand_secondary_color', '#FF8A00'),
            'currency': ConfigurationService.get_str('business.currency', 'KES'),
        },
    }


@method_decorator(ensure_csrf_cookie, name='dispatch')
class SpaIndexView(View):
    """
    Serves the CDN-based Material UI Single Page Application shell at /app/.
    """
    def get(self, request, *args, **kwargs):
        context = {
            'sacco_name': ConfigurationService.get_str('business.sacco_name', 'Northern Highways Transporters SACCO'),
            'primary_color': ConfigurationService.get_str('app.brand_primary_color', '#10315C'),
            'secondary_color': ConfigurationService.get_str('app.brand_secondary_color', '#FF8A00'),
            'currency': ConfigurationService.get_str('business.currency', 'KES'),
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


class UserManagementViewSet(viewsets.ModelViewSet):
    """
    SuperAdmin user provisioning, role allocation, suspension, and login history.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserManagementSerializer
    permission_classes = [IsSystemAdmin]
    filterset_fields = ['role', 'is_active', 'is_verified']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']

    @action(detail=True, methods=['post'])
    def assign_role(self, request, pk=None):
        user_obj = self.get_object()
        new_role = request.data.get('role')
        if new_role not in UserRole.values:
            return Response({'error': f"Invalid role '{new_role}'."}, status=status.HTTP_400_BAD_REQUEST)
        old_role = user_obj.role
        user_obj.role = new_role
        user_obj.save()
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='UserRole',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Changed role of {user_obj.username} from {old_role} to {new_role}",
        )
        return Response(UserManagementSerializer(user_obj).data)

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        user_obj = self.get_object()
        if user_obj.pk == request.user.pk:
            return Response({'error': 'You cannot deactivate your own active session.'}, status=status.HTTP_400_BAD_REQUEST)
        user_obj.is_active = not user_obj.is_active
        user_obj.save(update_fields=['is_active'])
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='UserStatus',
            entity_id=str(user_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"{'Activated' if user_obj.is_active else 'Suspended'} account {user_obj.username}",
        )
        return Response(UserManagementSerializer(user_obj).data)

    @action(detail=False, methods=['get'])
    def roles(self, request):
        return Response([{'value': k, 'label': str(v)} for k, v in UserRole.choices])

    @action(detail=False, methods=['get'])
    def login_history(self, request):
        logs = LoginHistory.objects.all().order_by('-timestamp')[:50]
        return Response(LoginHistorySerializer(logs, many=True).data)


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

        return Response({
            'kpis': {
                'total_members': kpis['total_members'],
                'active_members': kpis['active_members'],
                'pending_members': kpis['pending_members'],
                'total_vehicles': kpis['total_vehicles'],
                'compliant_vehicles': kpis['compliant_vehicles'],
                'delinquent_vehicles': kpis['delinquent_vehicles'],
                'compliance_rate': kpis['compliance_rate'],
                'expiring_docs': kpis['expiring_docs'],
                'expired_docs': kpis['expired_docs'],
                'financials': financials,
                'route_distribution': kpis['route_distribution'],
            },
            'fleet_categories': fleet_categories,
            'recent_audit': recent_audit,
        })
