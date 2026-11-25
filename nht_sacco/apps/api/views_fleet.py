from datetime import date, timedelta
from decimal import Decimal
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.accounts.permissions import (
    COMPLIANCE_STAFF_ROLES,
    REGISTRY_OPS_ROLES,
    RENEWAL_STAFF_ROLES,
    IsDriverUser,
    role_permission_factory,
)
from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.billing.models import Invoice, InvoiceItem, ServiceItem
from nht_sacco.apps.compliance.models import ComplianceAlert
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.documents.models import Document, DocumentType, DocumentVerification, VerificationStatus
from nht_sacco.apps.drivers.models import Driver, DriverAssignment
from nht_sacco.apps.integrations.branding import DocumentBrandingService
from nht_sacco.apps.integrations.models import CompanyProfile
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
from nht_sacco.apps.routes.models import Route, VehicleRouteAssignment
from nht_sacco.apps.vehicles.models import (
    ComplianceCardStatus,
    Vehicle,
    VehicleComplianceCard,
    VehicleOwnershipHistory,
    VehicleStatus,
)
from nht_sacco.apps.vehicles.services import ComplianceCardService
from .serializers import (
    ComplianceAlertSerializer,
    DocumentSerializer,
    DocumentTypeSerializer,
    DriverAssignmentSerializer,
    DriverSerializer,
    MemberSerializer,
    RenewalRequestSerializer,
    RouteSerializer,
    VehicleComplianceCardSerializer,
    VehicleOwnershipHistorySerializer,
    VehicleRouteAssignmentSerializer,
    VehicleSerializer,
)

RegistryOpsPermission = role_permission_factory(REGISTRY_OPS_ROLES, allow_auditor_read=True)
FleetReadAllStaff = role_permission_factory(
    REGISTRY_OPS_ROLES | COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES | {UserRole.TREASURER, UserRole.ACCOUNTANT, UserRole.MEMBER},
    allow_auditor_read=True,
)
CompliancePermission = role_permission_factory(COMPLIANCE_STAFF_ROLES, allow_auditor_read=True)


class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.select_related('user').order_by('-created_at')
    serializer_class = MemberSerializer
    permission_classes = [role_permission_factory(REGISTRY_OPS_ROLES | {UserRole.TREASURER, UserRole.ACCOUNTANT, UserRole.MEMBER}, allow_auditor_read=True)]
    filterset_fields = ['status', 'category', 'county']
    search_fields = ['membership_number', 'first_name', 'last_name', 'national_id', 'phone_number', 'email']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER:
            if hasattr(user, 'member_profile'):
                return qs.filter(pk=user.member_profile.pk)
            return qs.none()
        return qs

    def create(self, request, *args, **kwargs):
        if request.user.role in (UserRole.MEMBER, UserRole.DRIVER, UserRole.AUDITOR) and not request.user.is_superuser:
            return Response({'error': 'Insufficient privileges to register members.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        from nht_sacco.apps.accounts.models import User
        user_obj = serializer.validated_data.get('user')
        if not user_obj:
            base_uname = (
                serializer.validated_data.get('email', '').split('@')[0]
                or serializer.validated_data.get('national_id')
                or 'member'
            ).lower().replace(' ', '_')[:30]
            uname = base_uname
            suffix = 1
            while User.objects.filter(username=uname).exists():
                uname = f"{base_uname}_{suffix}"
                suffix += 1
            user_obj = User.objects.create(
                username=uname,
                email=serializer.validated_data['email'],
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name'],
                phone_number=serializer.validated_data.get('phone_number'),
                national_id=serializer.validated_data.get('national_id'),
                role=UserRole.MEMBER,
                is_staff=False,
                is_superuser=False,
                must_change_password=True,
            )
            user_obj.set_unusable_password()
            user_obj.save()
        member = serializer.save(
            user=user_obj,
            membership_number=Member.generate_membership_number(),
        )
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='Member',
            entity_id=member.membership_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Registered member {member.full_name}",
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in REGISTRY_OPS_ROLES):
            return Response({'error': 'Registry / Executive clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        member = self.get_object()
        member.approve(request.user, notes=request.data.get('notes', 'Approved via SPA'))
        return Response(MemberSerializer(member).data)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in REGISTRY_OPS_ROLES):
            return Response({'error': 'Registry / Executive clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        member = self.get_object()
        member.suspend(request.user, reason=request.data.get('reason', 'Administrative suspension'))
        return Response(MemberSerializer(member).data)

    @action(detail=True, methods=['post'])
    def reinstate(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in REGISTRY_OPS_ROLES):
            return Response({'error': 'Registry / Executive clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        member = self.get_object()
        member.reinstate(request.user)
        return Response(MemberSerializer(member).data)

    @action(detail=True, methods=['get'])
    def certificate_pdf(self, request, pk=None):
        member = self.get_object()
        reissue = request.query_params.get('reissue') in ('1', 'true', 'yes')
        if not member.branding_version_id or (reissue and (request.user.is_superuser or request.user.role in REGISTRY_OPS_ROLES)):
            member.branding_version = CompanyProfile.get_active().get_latest_version()
            member.save(update_fields=['branding_version', 'updated_at'])
        pdf_bytes = DocumentBrandingService.generate_membership_certificate_pdf(
            member,
            branding_version=member.branding_version,
        )
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.EXPORT,
            entity_type='MembershipCertificatePDF',
            entity_id=member.membership_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Generated membership certificate PDF for {member.membership_number} (reissue={reissue})",
        )
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="NHT_Membership_{member.membership_number}.pdf"'
        return resp


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related('current_owner').order_by('registration_number')
    serializer_class = VehicleSerializer
    permission_classes = [FleetReadAllStaff]
    filterset_fields = ['status', 'category', 'current_owner']
    search_fields = ['registration_number', 'chassis_number', 'make', 'model']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER:
            if hasattr(user, 'member_profile'):
                return qs.filter(current_owner=user.member_profile)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'created_by': user}
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile'):
            kwargs['current_owner'] = user.member_profile
            kwargs['status'] = VehicleStatus.PENDING
        vehicle = serializer.save(**kwargs)
        AuditLog.log_action(
            actor=user,
            action=AuditAction.CREATE,
            entity_type='Vehicle',
            entity_id=vehicle.registration_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Registered vehicle {vehicle.registration_number}",
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def transfer_ownership(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in REGISTRY_OPS_ROLES):
            return Response({'error': 'Registry / Operations clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        vehicle = self.get_object()
        new_owner_id = request.data.get('new_owner')
        reason = request.data.get('reason', '')
        new_owner = Member.objects.filter(pk=new_owner_id).first()
        if not new_owner:
            return Response({'error': 'Target member not found.'}, status=status.HTTP_404_NOT_FOUND)
        if new_owner.pk == vehicle.current_owner_id:
            return Response({'error': 'Vehicle is already owned by this member.'}, status=status.HTTP_400_BAD_REQUEST)

        prev_owner = vehicle.current_owner
        VehicleOwnershipHistory.objects.create(
            vehicle=vehicle,
            previous_owner=prev_owner,
            new_owner=new_owner,
            transfer_reason=reason,
            authorized_by=request.user,
        )
        vehicle.current_owner = new_owner
        vehicle.save(update_fields=['current_owner', 'updated_at'])
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='VehicleOwnership',
            entity_id=vehicle.registration_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Transferred {vehicle.registration_number} from {prev_owner.membership_number} to {new_owner.membership_number}",
        )
        return Response(VehicleSerializer(vehicle).data)

    @action(detail=True, methods=['get'])
    def compliance_detail(self, request, pk=None):
        vehicle = self.get_object()
        comp = ComplianceService.get_vehicle_compliance_status(vehicle)
        return Response({
            'vehicle': vehicle.registration_number,
            'status': comp['status'],
            'missing_mandatory': [dt.name for dt in comp['missing_mandatory']],
            'expired_docs': [{'id': str(d.pk), 'type': d.document_type.name, 'expiry_date': str(d.expiry_date)} for d in comp['expired_docs']],
            'expiring_soon_docs': [{'id': str(d.pk), 'type': d.document_type.name, 'expiry_date': str(d.expiry_date)} for d in comp['expiring_soon_docs']],
            'valid_docs': [{'id': str(d.pk), 'type': d.document_type.name, 'expiry_date': str(d.expiry_date)} for d in comp['valid_docs']],
            'verify_url': request.build_absolute_uri(f"/verify/vehicle/{vehicle.qr_token}/"),
        })

    @action(detail=True, methods=['get'])
    def ownership_history(self, request, pk=None):
        vehicle = self.get_object()
        qs = vehicle.ownership_history.select_related('previous_owner', 'new_owner', 'authorized_by').all()
        return Response(VehicleOwnershipHistorySerializer(qs, many=True).data)


class VehicleComplianceCardViewSet(viewsets.ModelViewSet):
    """
    Lifecycle management for digital Vehicle Compliance Cards & Cryptographic QR Tokens.
    Supports issuing, viewing, renewing, revoking, suspending, reinstating, QR token rotation,
    and branded PDF export while keeping public verification zero-PII.
    """
    queryset = VehicleComplianceCard.objects.select_related(
        'vehicle', 'vehicle__current_owner', 'issued_by', 'revoked_by', 'branding_version'
    ).order_by('-created_at')
    serializer_class = VehicleComplianceCardSerializer
    permission_classes = [role_permission_factory(
        COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES | REGISTRY_OPS_ROLES | {UserRole.MEMBER},
        allow_auditor_read=True,
    )]
    filterset_fields = ['status', 'vehicle']
    search_fields = ['certificate_number', 'fleet_number', 'vehicle__registration_number', 'owner_display_name', 'assigned_route_name']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER:
            if hasattr(user, 'member_profile'):
                return qs.filter(vehicle__current_owner=user.member_profile)
            return qs.none()
        return qs

    @staticmethod
    def _parse_expiry_date(raw_val):
        if not raw_val:
            return None
        if isinstance(raw_val, date):
            return raw_val
        return date.fromisoformat(str(raw_val).strip())

    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in (COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES | REGISTRY_OPS_ROLES)):
            return Response({'error': 'Compliance or Operations officer clearance required to issue compliance cards.'}, status=status.HTTP_403_FORBIDDEN)

        vehicle_id = request.data.get('vehicle')
        vehicle = Vehicle.objects.select_related('current_owner').filter(pk=vehicle_id).first()
        if not vehicle:
            return Response({'error': 'Target vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            expiry_date = self._parse_expiry_date(request.data.get('expiry_date'))
        except ValueError:
            return Response({'error': 'Invalid expiry_date format (expected YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

        card, _ = ComplianceCardService.issue_card(
            vehicle=vehicle,
            issued_by=request.user,
            expiry_date=expiry_date,
            fleet_number=(request.data.get('fleet_number') or '').strip(),
            notes=(request.data.get('notes') or '').strip(),
            supersede_existing=bool(request.data.get('supersede_existing', True)),
        )
        return Response(
            VehicleComplianceCardSerializer(card, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in (COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES)):
            return Response({'error': 'Compliance or Renewal officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        card = self.get_object()
        try:
            expiry_date = self._parse_expiry_date(request.data.get('expiry_date'))
        except ValueError:
            return Response({'error': 'Invalid expiry_date format (expected YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)
        new_card, _ = ComplianceCardService.renew_card(
            old_card=card,
            issued_by=request.user,
            expiry_date=expiry_date,
            notes=(request.data.get('notes') or '').strip(),
        )
        return Response(
            VehicleComplianceCardSerializer(new_card, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        card = self.get_object()
        updated = ComplianceCardService.revoke_card(
            card=card,
            revoked_by=request.user,
            reason=(request.data.get('reason') or 'Administrative revocation').strip(),
        )
        return Response(VehicleComplianceCardSerializer(updated, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        card = self.get_object()
        updated = ComplianceCardService.suspend_card(
            card=card,
            actor=request.user,
            reason=(request.data.get('reason') or '').strip(),
        )
        return Response(VehicleComplianceCardSerializer(updated, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def reinstate(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        card = self.get_object()
        updated = ComplianceCardService.reinstate_card(
            card=card,
            actor=request.user,
            notes=(request.data.get('notes') or '').strip(),
        )
        return Response(VehicleComplianceCardSerializer(updated, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def regenerate_qr(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        card = self.get_object()
        updated, _ = ComplianceCardService.regenerate_qr(card=card, actor=request.user)
        return Response(VehicleComplianceCardSerializer(updated, context={'request': request}).data)

    @action(detail=True, methods=['get'])
    def download_pdf(self, request, pk=None):
        card = self.get_object()
        verify_url = ComplianceCardService.get_verify_url(card, request=request)
        qr_png = ComplianceCardService.get_qr_png_bytes(card, request=request)
        pdf_bytes = DocumentBrandingService.generate_compliance_card_pdf(
            card=card,
            verify_url=verify_url,
            qr_png_bytes=qr_png,
        )
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.EXPORT,
            entity_type='VehicleComplianceCardPDF',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Exported compliance card PDF {card.certificate_number}",
        )
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="NHT_Compliance_Card_{card.certificate_number}.pdf"'
        return resp

    @action(detail=False, methods=['get'])
    def stats(self, request):
        today = timezone.localdate()
        in_30 = today + timedelta(days=30)
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'valid': qs.filter(status=ComplianceCardStatus.VALID, expiry_date__gte=today).count(),
            'expiring_30_days': qs.filter(status=ComplianceCardStatus.VALID, expiry_date__gte=today, expiry_date__lte=in_30).count(),
            'expired': qs.filter(status=ComplianceCardStatus.EXPIRED).count() + qs.filter(status=ComplianceCardStatus.VALID, expiry_date__lt=today).count(),
            'revoked': qs.filter(status=ComplianceCardStatus.REVOKED).count(),
            'suspended': qs.filter(status=ComplianceCardStatus.SUSPENDED).count(),
            'superseded': qs.filter(status=ComplianceCardStatus.SUPERSEDED).count(),
        })


class DriverViewSet(viewsets.ModelViewSet):
    queryset = Driver.objects.select_related('user').order_by('full_name')
    serializer_class = DriverSerializer
    permission_classes = [role_permission_factory(REGISTRY_OPS_ROLES | COMPLIANCE_STAFF_ROLES, allow_auditor_read=True)]
    filterset_fields = ['status']
    search_fields = ['full_name', 'national_id', 'driving_license_number', 'phone_number']


class DriverAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DriverAssignment.objects.select_related('driver', 'vehicle').order_by('-assigned_at')
    serializer_class = DriverAssignmentSerializer
    permission_classes = [RegistryOpsPermission]
    filterset_fields = ['is_current', 'driver', 'vehicle']

    def perform_create(self, serializer):
        driver = serializer.validated_data['driver']
        DriverAssignment.objects.filter(driver=driver, is_current=True).update(
            is_current=False,
            relieved_at=timezone.now(),
        )
        serializer.save(assigned_by=self.request.user, is_current=True)

    @action(detail=True, methods=['post'])
    def relieve(self, request, pk=None):
        assign = self.get_object()
        assign.relieve()
        return Response(DriverAssignmentSerializer(assign).data)


class DriverPortalAPIView(APIView):
    """
    Self-service read-only endpoint for PSV Drivers (UserRole.DRIVER).
    """
    permission_classes = [IsDriverUser]

    def get(self, request):
        driver = getattr(request.user, 'driver_profile', None)
        if not driver:
            return Response({'error': 'No driver profile linked to your account.'}, status=status.HTTP_404_NOT_FOUND)

        assignments = DriverAssignment.objects.filter(driver=driver, is_current=True).select_related('vehicle', 'vehicle__current_owner')
        assigned_vehicles = []
        for a in assignments:
            v = a.vehicle
            comp = ComplianceService.get_vehicle_compliance_status(v)
            route_alloc = v.route_allocations.filter(is_active=True).select_related('route').first()
            assigned_vehicles.append({
                'vehicle_id': str(v.pk),
                'registration_number': v.registration_number,
                'make_model': f"{v.make} {v.model}",
                'category': v.get_category_display(),
                'owner_name': v.current_owner.full_name,
                'compliance_status': comp['status'],
                'route': f"{route_alloc.route.route_code}: {route_alloc.route.name}" if route_alloc else 'Unassigned',
                'qr_verify_url': f"/verify/vehicle/{v.qr_token}/",
            })

        today = timezone.localdate()
        driver_docs = Document.objects.filter(driver=driver).select_related('document_type').order_by('-expiry_date')
        return Response({
            'driver': DriverSerializer(driver).data,
            'dl_days_remaining': (driver.dl_expiry_date - today).days if driver.dl_expiry_date else None,
            'psv_days_remaining': (driver.psv_badge_expiry - today).days if driver.psv_badge_expiry else None,
            'assigned_vehicles': assigned_vehicles,
            'driver_documents': DocumentSerializer(driver_docs, many=True).data,
        })


class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all().order_by('route_code')
    serializer_class = RouteSerializer
    permission_classes = [RegistryOpsPermission]
    filterset_fields = ['is_active']
    search_fields = ['route_code', 'name', 'origin', 'destination']


class VehicleRouteAssignmentViewSet(viewsets.ModelViewSet):
    queryset = VehicleRouteAssignment.objects.select_related('vehicle', 'route').order_by('-assigned_date')
    serializer_class = VehicleRouteAssignmentSerializer
    permission_classes = [RegistryOpsPermission]
    filterset_fields = ['is_active', 'route', 'vehicle']

    def perform_create(self, serializer):
        serializer.save(authorized_by=self.request.user)


class DocumentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DocumentType.objects.all().order_by('name')
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related('document_type', 'vehicle', 'member', 'driver').order_by('-created_at')
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [role_permission_factory(COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES | {UserRole.SECRETARY, UserRole.MEMBER}, allow_auditor_read=True)]
    filterset_fields = ['status', 'document_type', 'vehicle', 'driver']
    search_fields = ['reference_number', 'vehicle__registration_number', 'document_type__name']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER:
            if hasattr(user, 'member_profile'):
                return qs.filter(vehicle__current_owner=user.member_profile) | qs.filter(member=user.member_profile)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        doc_type = serializer.validated_data['document_type']
        vehicle = serializer.validated_data.get('vehicle')
        driver = serializer.validated_data.get('driver')
        member = serializer.validated_data.get('member')
        if self.request.user.role == UserRole.MEMBER and hasattr(self.request.user, 'member_profile'):
            member = self.request.user.member_profile
        latest = Document.objects.filter(
            document_type=doc_type,
            vehicle=vehicle,
            driver=driver,
            member=member,
        ).order_by('-version').first()
        next_ver = (latest.version + 1) if latest else 1
        doc = serializer.save(
            member=member,
            uploaded_by=self.request.user,
            version=next_ver,
            status=VerificationStatus.PENDING,
        )
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='Document',
            entity_id=str(doc.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Uploaded v{next_ver} of {doc_type.name} ({doc.reference_number})",
        )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        doc = self.get_object()
        decision = request.data.get('decision', 'APPROVED')
        notes = request.data.get('notes', '')
        if decision not in ('APPROVED', 'REJECTED'):
            return Response({'error': 'Decision must be APPROVED or REJECTED.'}, status=status.HTTP_400_BAD_REQUEST)

        doc.status = VerificationStatus.VERIFIED if decision == 'APPROVED' else VerificationStatus.REJECTED
        doc.verified_by = request.user
        doc.verification_date = timezone.now()
        doc.verification_notes = notes
        doc.save()

        DocumentVerification.objects.create(
            document=doc,
            reviewed_by=request.user,
            decision=decision,
            notes=notes or f"Reviewed via SPA ({decision})",
        )
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.APPROVE if decision == 'APPROVED' else AuditAction.REJECT,
            entity_type='Document',
            entity_id=str(doc.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Document {doc.reference_number} marked {doc.status}",
        )
        return Response(DocumentSerializer(doc).data)


class ComplianceAlertViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ComplianceAlert.objects.select_related('vehicle', 'document', 'recipient_member').order_by('-created_at')
    serializer_class = ComplianceAlertSerializer
    permission_classes = [role_permission_factory(COMPLIANCE_STAFF_ROLES | RENEWAL_STAFF_ROLES | {UserRole.SECRETARY, UserRole.MEMBER}, allow_auditor_read=True)]
    filterset_fields = ['alert_type', 'is_resolved', 'vehicle']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == UserRole.MEMBER:
            if hasattr(self.request.user, 'member_profile'):
                return qs.filter(recipient_member=self.request.user.member_profile)
            return qs.none()
        return qs

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        alert = self.get_object()
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['is_resolved', 'resolved_at'])
        return Response(ComplianceAlertSerializer(alert).data)


class ComplianceScanAPIView(APIView):
    permission_classes = [CompliancePermission]

    def post(self, request):
        result = ComplianceService.run_daily_compliance_scan()
        return Response(result, status=status.HTTP_200_OK)


class RenewalRequestViewSet(viewsets.ModelViewSet):
    queryset = RenewalRequest.objects.select_related('member', 'vehicle', 'document_type', 'invoice', 'assigned_officer').order_by('-created_at')
    serializer_class = RenewalRequestSerializer
    permission_classes = [role_permission_factory(RENEWAL_STAFF_ROLES | COMPLIANCE_STAFF_ROLES | {UserRole.MEMBER}, allow_auditor_read=True)]
    filterset_fields = ['status', 'vehicle', 'document_type']
    search_fields = ['request_number', 'vehicle__registration_number', 'member__first_name', 'member__last_name']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == UserRole.MEMBER:
            if hasattr(self.request.user, 'member_profile'):
                return qs.filter(member=self.request.user.member_profile)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        vehicle = serializer.validated_data['vehicle']
        member = self.request.user.member_profile if (self.request.user.role == UserRole.MEMBER and hasattr(self.request.user, 'member_profile')) else vehicle.current_owner
        doc_type = serializer.validated_data['document_type']
        current_doc = Document.objects.filter(vehicle=vehicle, document_type=doc_type).order_by('-expiry_date').first()
        req = serializer.save(
            request_number=RenewalRequest.generate_request_number(),
            member=member,
            current_document=current_doc,
            status=RenewalStatus.SUBMITTED,
        )
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='RenewalRequest',
            entity_id=req.request_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Created renewal request {req.request_number}",
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def review_invoice(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in RENEWAL_STAFF_ROLES):
            return Response({'error': 'Renewal Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        renewal = self.get_object()
        act = request.data.get('action', 'APPROVE_INVOICE')
        if act == 'REJECT':
            renewal.status = RenewalStatus.REJECTED
            renewal.notes = request.data.get('notes', renewal.notes)
            renewal.save()
            return Response(RenewalRequestSerializer(renewal).data)

        today = timezone.localdate()
        fee = Decimal(str(request.data.get('fee', '1000.00')))
        invoice = Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            member=renewal.member,
            vehicle=renewal.vehicle,
            issue_date=today,
            due_date=today + timezone.timedelta(days=7),
            notes=f"Renewal fee for {renewal.document_type.name} on {renewal.vehicle.registration_number}",
            created_by=request.user,
        )
        service = ServiceItem.objects.filter(category='RENEWAL', is_active=True).first() or ServiceItem.objects.filter(is_active=True).first()
        if service:
            InvoiceItem.objects.create(
                invoice=invoice,
                service_item=service,
                description=f"{renewal.document_type.name} Renewal Fee",
                unit_price=fee,
                quantity=1,
            )
            invoice.recalculate_totals()
        renewal.mark_reviewed(officer_user=request.user, invoice=invoice)
        return Response(RenewalRequestSerializer(renewal).data)

    @action(detail=True, methods=['post'])
    def mark_processing(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in RENEWAL_STAFF_ROLES):
            return Response({'error': 'Renewal Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        renewal = self.get_object()
        renewal.mark_processing()
        return Response(RenewalRequestSerializer(renewal).data)

    @action(detail=True, methods=['post'])
    def attach_document(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in (RENEWAL_STAFF_ROLES | COMPLIANCE_STAFF_ROLES)):
            return Response({'error': 'Renewal / Compliance Officer clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        renewal = self.get_object()
        doc_id = request.data.get('document_id')
        doc = Document.objects.filter(pk=doc_id).first()
        if not doc:
            return Response({'error': 'Replacement document not found.'}, status=status.HTTP_404_NOT_FOUND)
        renewal.upload_replacement_document(doc)
        return Response(RenewalRequestSerializer(renewal).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in COMPLIANCE_STAFF_ROLES):
            return Response({'error': 'Compliance Officer clearance required to finalize renewal.'}, status=status.HTTP_403_FORBIDDEN)
        renewal = self.get_object()
        renewal.complete_renewal(request.user)
        return Response(RenewalRequestSerializer(renewal).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        renewal = self.get_object()
        if self.request.user.role == UserRole.MEMBER and hasattr(self.request.user, 'member_profile') and renewal.member != self.request.user.member_profile:
            return Response({'error': 'Access Denied.'}, status=status.HTTP_403_FORBIDDEN)
        if renewal.status not in (RenewalStatus.SUBMITTED, RenewalStatus.UNDER_REVIEW, RenewalStatus.INVOICED):
            return Response({'error': f"Cannot cancel renewal in status {renewal.status}."}, status=status.HTTP_400_BAD_REQUEST)
        renewal.status = RenewalStatus.CANCELLED
        renewal.save(update_fields=['status', 'updated_at'])
        return Response(RenewalRequestSerializer(renewal).data)
