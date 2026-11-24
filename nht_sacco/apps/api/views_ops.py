from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.accounts.permissions import (
    COMPLIANCE_STAFF_ROLES,
    FINANCE_CHECKER_ROLES,
    MANAGEMENT_ROLES,
    REGISTRY_OPS_ROLES,
    IsAuditorReadOnly,
    IsManagementStaff,
    role_permission_factory,
)
from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.governance.models import Committee, Meeting, Resolution, ResolutionStatus
from nht_sacco.apps.governance.services import GovernanceService
from nht_sacco.apps.incidents.models import Incident, IncidentStatus, IncidentUpdate
from nht_sacco.apps.maintenance.models import MaintenanceProvider, MaintenanceRecord, SparePart
from nht_sacco.apps.maintenance.services import MaintenanceService
from nht_sacco.apps.notifications.models import (
    Announcement,
    CommunicationPreference,
    Notification,
    NotificationCategory,
)
from nht_sacco.apps.notifications.services import NotificationDispatcherService
from nht_sacco.apps.reports.services import ExecutiveDashboardMetrics
from .serializers import (
    AnnouncementSerializer,
    AuditLogSerializer,
    CommitteeSerializer,
    CommunicationPreferenceSerializer,
    IncidentSerializer,
    MaintenanceProviderSerializer,
    MaintenanceRecordSerializer,
    MeetingSerializer,
    NotificationSerializer,
    ResolutionSerializer,
    SparePartSerializer,
)

OpsWritePermission = role_permission_factory(
    REGISTRY_OPS_ROLES | COMPLIANCE_STAFF_ROLES,
    allow_auditor_read=True,
)


class MaintenanceProviderViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceProvider.objects.all().order_by('name')
    serializer_class = MaintenanceProviderSerializer
    permission_classes = [OpsWritePermission]
    search_fields = ['name', 'physical_address', 'specialty']


class SparePartViewSet(viewsets.ModelViewSet):
    queryset = SparePart.objects.all().order_by('name')
    serializer_class = SparePartSerializer
    permission_classes = [OpsWritePermission]
    search_fields = ['name', 'part_number', 'category']


class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    queryset = MaintenanceRecord.objects.select_related('vehicle', 'provider').order_by('-scheduled_date', '-created_at')
    serializer_class = MaintenanceRecordSerializer
    permission_classes = [OpsWritePermission]
    filterset_fields = ['status', 'maintenance_type', 'vehicle']
    search_fields = ['work_order_number', 'vehicle__registration_number', 'description']

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        rec = self.get_object()
        updated = MaintenanceService.complete_service(
            record=rec,
            verified_by=request.user,
            downtime_hours=request.data.get('downtime_hours'),
            notes=request.data.get('notes'),
        )
        return Response(MaintenanceRecordSerializer(updated).data)


class IncidentViewSet(viewsets.ModelViewSet):
    queryset = Incident.objects.select_related('vehicle', 'reported_by_member', 'assigned_officer').prefetch_related('updates').order_by('-created_at')
    serializer_class = IncidentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'severity', 'incident_type']
    search_fields = ['ticket_number', 'title', 'description']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile'):
            return qs.filter(reported_by_member=user.member_profile)
        if user.role == UserRole.DRIVER and hasattr(user, 'driver_profile'):
            return qs.filter(driver=user.driver_profile)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile'):
            kwargs['reported_by_member'] = user.member_profile
        elif user.role == UserRole.DRIVER and hasattr(user, 'driver_profile'):
            kwargs['driver'] = user.driver_profile
        inc = serializer.save(**kwargs)
        AuditLog.log_action(
            actor=user,
            action=AuditAction.CREATE,
            entity_type='Incident',
            entity_id=inc.ticket_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Incident ticket {inc.ticket_number} created",
        )

    @action(detail=True, methods=['post'])
    def add_update(self, request, pk=None):
        if request.user.role in (UserRole.MEMBER, UserRole.DRIVER, UserRole.AUDITOR) and not request.user.is_superuser:
            return Response({'error': 'Officer privileges required.'}, status=status.HTTP_403_FORBIDDEN)
        inc = self.get_object()
        notes = (request.data.get('notes') or '').strip()
        new_status = request.data.get('status') or ''
        if not notes:
            return Response({'error': 'Update notes are required.'}, status=status.HTTP_400_BAD_REQUEST)
        IncidentUpdate.objects.create(incident=inc, author=request.user, notes=notes, status_change=new_status)
        if new_status and new_status in IncidentStatus.values:
            inc.status = new_status
            if new_status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                inc.resolved_at = timezone.now()
                inc.resolution_notes = notes
            inc.save()
        return Response(IncidentSerializer(inc).data)


class CommitteeViewSet(viewsets.ModelViewSet):
    queryset = Committee.objects.select_related('chairperson', 'secretary').order_by('name')
    serializer_class = CommitteeSerializer
    permission_classes = [role_permission_factory({UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.SECRETARY}, allow_auditor_read=True)]


class MeetingViewSet(viewsets.ModelViewSet):
    queryset = Meeting.objects.select_related('committee').order_by('-scheduled_date')
    serializer_class = MeetingSerializer
    permission_classes = [role_permission_factory({UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.SECRETARY}, allow_auditor_read=True)]

    def perform_create(self, serializer):
        serializer.save(convened_by=self.request.user)


class ResolutionViewSet(viewsets.ModelViewSet):
    queryset = Resolution.objects.select_related('meeting').order_by('-created_at')
    serializer_class = ResolutionSerializer
    permission_classes = [role_permission_factory({UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.SECRETARY}, allow_auditor_read=True)]

    @action(detail=True, methods=['post'])
    def record_vote(self, request, pk=None):
        res = self.get_object()
        res.votes_for = int(request.data.get('votes_for', res.votes_for))
        res.votes_against = int(request.data.get('votes_against', res.votes_against))
        res.votes_abstained = int(request.data.get('votes_abstained', res.votes_abstained))
        if res.votes_for > res.votes_against:
            res.status = ResolutionStatus.PASSED
        elif res.votes_against >= res.votes_for and (res.votes_for + res.votes_against) > 0:
            res.status = ResolutionStatus.REJECTED
        res.save()
        return Response(ResolutionSerializer(res).data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.all().order_by('-created_at')
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == UserRole.SUPER_ADMIN:
            return super().get_queryset()[:100]
        return Notification.objects.filter(recipient_user=user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        if notif.recipient_user_id != request.user.id and not request.user.is_superuser:
            return Response({'error': 'Access Denied.'}, status=status.HTTP_403_FORBIDDEN)
        notif.mark_as_read()
        return Response(NotificationSerializer(notif).data)


class CommunicationPreferenceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'member_profile'):
            return Response({'error': 'Communication preferences apply to SACCO Members.'}, status=status.HTTP_404_NOT_FOUND)
        pref, _ = CommunicationPreference.objects.get_or_create(member=request.user.member_profile)
        return Response(CommunicationPreferenceSerializer(pref).data)

    def put(self, request):
        if not hasattr(request.user, 'member_profile'):
            return Response({'error': 'Communication preferences apply to SACCO Members.'}, status=status.HTTP_404_NOT_FOUND)
        pref, _ = CommunicationPreference.objects.get_or_create(member=request.user.member_profile)
        ser = CommunicationPreferenceSerializer(pref, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    queryset = Announcement.objects.all().order_by('-created_at')
    serializer_class = AnnouncementSerializer
    permission_classes = [role_permission_factory({UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.SECRETARY}, allow_auditor_read=True)]

    def perform_create(self, serializer):
        ann = serializer.save(published_by=self.request.user)
        if ann.is_published and self.request.data.get('broadcast', True):
            from nht_sacco.apps.members.models import Member, MembershipStatus
            channels = ['IN_APP']
            if self.request.data.get('send_sms'):
                channels.append('SMS')
            if self.request.data.get('send_email'):
                channels.append('EMAIL')
            for m in Member.objects.filter(status=MembershipStatus.ACTIVE):
                NotificationDispatcherService.dispatch_to_member(
                    member=m,
                    category=NotificationCategory.ANNOUNCEMENT,
                    title=ann.title,
                    message=ann.content,
                    channels=channels,
                )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all().order_by('-timestamp')
    serializer_class = AuditLogSerializer
    permission_classes = [role_permission_factory({UserRole.SUPER_ADMIN, UserRole.CHAIRMAN}, allow_auditor_read=True)]
    filterset_fields = ['action', 'entity_type', 'outcome']
    search_fields = ['actor_username', 'entity_type', 'entity_id']


class ReportSummaryAPIView(APIView):
    permission_classes = [IsManagementStaff]

    def get(self, request):
        kpis = ExecutiveDashboardMetrics.get_kpis()
        gov = GovernanceService.get_governance_summary()
        maint = MaintenanceService.get_fleet_maintenance_metrics()
        can_export_finance = request.user.is_superuser or request.user.role in (
            FINANCE_CHECKER_ROLES | {UserRole.AUDITOR}
        )
        return Response({
            'compliance_pdf_url': '/reports/export/compliance-pdf/',
            'financial_excel_url': '/reports/export/financial-excel/' if can_export_finance else None,
            'can_export_finance': can_export_finance,
            'governance_summary': gov,
            'maintenance_summary': {k: str(v) for k, v in maint.items()},
            'total_vehicles': kpis['total_vehicles'],
            'compliance_rate': kpis['compliance_rate'],
        })
