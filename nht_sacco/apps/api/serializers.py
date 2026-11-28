from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers

from nht_sacco.apps.accounts.models import User, UserRole, LoginHistory
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.vehicles.models import Vehicle, VehicleCategory, FuelType, VehicleOwnershipHistory, VehicleComplianceCard
from nht_sacco.apps.drivers.models import Driver, DriverAssignment
from nht_sacco.apps.routes.models import Route, VehicleRouteAssignment
from nht_sacco.apps.documents.models import Document, DocumentType
from nht_sacco.apps.compliance.models import ComplianceAlert
from nht_sacco.apps.renewals.models import RenewalRequest
from nht_sacco.apps.billing.models import ServiceItem, Invoice, InvoiceItem, CreditNote
from nht_sacco.apps.payments.models import (
    Payment,
    Receipt,
    ManualPaymentVoucher,
    ReconciliationRun,
    ReconciliationException,
)
from nht_sacco.apps.accounting.models import Account, FinancialPeriod, JournalEntry, JournalLine, Expense
from nht_sacco.apps.maintenance.models import MaintenanceProvider, SparePart, MaintenanceRecord
from nht_sacco.apps.incidents.models import Incident, IncidentUpdate
from nht_sacco.apps.governance.models import Committee, Meeting, Resolution
from nht_sacco.apps.notifications.models import (
    Notification,
    NotificationTemplate,
    CommunicationPreference,
    Announcement,
)
from nht_sacco.apps.audit.models import AuditLog


class UserManagementSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    full_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=10)
    account_category = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'national_id',
            'role',
            'role_display',
            'account_category',
            'is_active',
            'is_verified',
            'is_staff',
            'is_superuser',
            'must_change_password',
            'last_login',
            'last_login_ip',
            'date_joined',
            'password',
        ]
        read_only_fields = ['id', 'is_staff', 'is_superuser', 'last_login', 'last_login_ip', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_account_category(self, obj):
        if obj.role in (UserRole.MEMBER, UserRole.DRIVER) and not obj.is_superuser:
            return 'OPERATIONAL_PORTAL'
        return 'SACCO_STAFF'

    def validate_role(self, value):
        request = self.context.get('request')
        actor = getattr(request, 'user', None)
        if value == UserRole.SUPER_ADMIN:
            if not actor or not (actor.is_superuser or actor.role == UserRole.SUPER_ADMIN):
                raise serializers.ValidationError("Only an active Super Administrator may assign the SUPER_ADMIN role.")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        new_role = validated_data.get('role', instance.role)
        new_active = validated_data.get('is_active', instance.is_active)
        was_active_super = instance.is_active and (instance.role == UserRole.SUPER_ADMIN or instance.is_superuser)
        will_be_active_super = new_active and (new_role == UserRole.SUPER_ADMIN or (instance.is_superuser and new_role == instance.role))
        if was_active_super and not will_be_active_super:
            from nht_sacco.apps.accounts.services import AccountSecurityService
            if not AccountSecurityService.other_active_super_admin_exists(instance.pk):
                raise serializers.ValidationError("Cannot deactivate or demote the last active Super Administrator.")
        if instance.role == UserRole.SUPER_ADMIN and new_role != UserRole.SUPER_ADMIN:
            instance.is_superuser = False
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LoginHistory
        fields = ['id', 'username_attempted', 'ip_address', 'status', 'timestamp']


class MemberSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    full_name = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')
    portal_active = serializers.BooleanField(source='user.is_active', read_only=True, default=False)
    has_portal_account = serializers.SerializerMethodField()
    vehicles = serializers.SerializerMethodField()
    vehicle_count = serializers.SerializerMethodField()
    portal_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    portal_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    must_change_password = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = Member
        fields = [
            'id', 'user', 'username', 'portal_active', 'has_portal_account',
            'portal_username', 'portal_password', 'must_change_password',
            'membership_number', 'first_name', 'middle_name', 'last_name',
            'full_name', 'national_id', 'phone_number', 'email', 'postal_address', 'county',
            'category', 'category_display', 'status', 'status_display',
            'next_of_kin_name', 'next_of_kin_relation', 'next_of_kin_phone',
            'vehicles', 'vehicle_count',
            'application_date', 'approval_date', 'approval_notes', 'created_at',
        ]
        read_only_fields = ['id', 'membership_number', 'application_date', 'approval_date', 'created_at']

    def get_has_portal_account(self, obj):
        return bool(obj.user_id and obj.user.is_active and obj.user.has_usable_password())

    def get_vehicles(self, obj):
        return [
            {
                'id': str(v.pk),
                'registration_number': v.registration_number,
                'chassis_number': v.chassis_number,
                'engine_number': v.engine_number,
                'make': v.make,
                'model': v.model,
                'year_of_manufacture': v.year_of_manufacture,
                'category': v.category,
                'category_display': v.get_category_display(),
                'fuel_type': v.fuel_type,
                'fuel_type_display': v.get_fuel_type_display(),
                'carrying_capacity': v.carrying_capacity,
                'color': v.color,
                'status': v.status,
                'qr_token': str(v.qr_token),
            }
            for v in obj.vehicles.all()
        ]

    def get_vehicle_count(self, obj):
        return obj.vehicles.count()


class VehicleSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='current_owner.full_name', read_only=True)
    owner_membership_no = serializers.CharField(source='current_owner.membership_number', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    fuel_type_display = serializers.CharField(source='get_fuel_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    compliance_status = serializers.SerializerMethodField()
    engine_number = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=50)

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'chassis_number', 'engine_number', 'make', 'model',
            'year_of_manufacture', 'category', 'category_display', 'fuel_type', 'fuel_type_display',
            'carrying_capacity', 'color', 'current_owner', 'owner_name', 'owner_membership_no',
            'status', 'status_display', 'qr_token', 'compliance_status', 'registered_at',
        ]
        read_only_fields = ['id', 'qr_token', 'registered_at']

    def validate_engine_number(self, value):
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    def validate(self, attrs):
        category = attrs.get('category', getattr(self.instance, 'category', VehicleCategory.HEAVY_TRUCK))
        fuel_type = attrs.get('fuel_type', getattr(self.instance, 'fuel_type', None))
        if category == VehicleCategory.SEMI_TRAILER and not fuel_type:
            attrs['fuel_type'] = FuelType.NONE
        return attrs

    def get_compliance_status(self, obj):
        from nht_sacco.apps.compliance.services import ComplianceService
        return ComplianceService.get_vehicle_compliance_status(obj)['status']


class VehicleOwnershipHistorySerializer(serializers.ModelSerializer):
    previous_owner_name = serializers.CharField(source='previous_owner.full_name', read_only=True)
    new_owner_name = serializers.CharField(source='new_owner.full_name', read_only=True)
    authorized_by_username = serializers.CharField(source='authorized_by.username', read_only=True, default='SYSTEM')

    class Meta:
        model = VehicleOwnershipHistory
        fields = ['id', 'vehicle', 'previous_owner', 'previous_owner_name', 'new_owner', 'new_owner_name', 'transfer_date', 'transfer_reason', 'authorized_by_username']


class VehicleComplianceCardSerializer(serializers.ModelSerializer):
    registration_number = serializers.CharField(source='vehicle.registration_number', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()
    vehicle_category = serializers.CharField(source='vehicle.get_category_display', read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    branding_version_number = serializers.IntegerField(source='branding_version.version_number', read_only=True, default=1)
    verify_url = serializers.SerializerMethodField()
    qr_data_uri = serializers.SerializerMethodField()

    class Meta:
        model = VehicleComplianceCard
        fields = [
            'id', 'vehicle', 'registration_number', 'vehicle_make_model', 'vehicle_category',
            'certificate_number', 'fleet_number', 'owner_display_name', 'assigned_route_name',
            'token_hint', 'status', 'status_display', 'issue_date', 'expiry_date',
            'issued_by', 'issued_by_name', 'revoked_by', 'revoked_at', 'revocation_reason',
            'superseded_by', 'branding_version_number', 'verify_url', 'qr_data_uri',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'certificate_number', 'token_hint', 'status', 'issued_by',
            'revoked_by', 'revoked_at', 'superseded_by', 'created_at', 'updated_at',
        ]

    def get_vehicle_make_model(self, obj):
        return f"{obj.vehicle.make} {obj.vehicle.model}"

    def get_issued_by_name(self, obj):
        if not obj.issued_by:
            return 'SACCO Compliance Desk'
        return obj.issued_by.get_full_name() or obj.issued_by.username

    def get_verify_url(self, obj):
        from nht_sacco.apps.vehicles.services import ComplianceCardService
        return ComplianceCardService.get_verify_url(obj, request=self.context.get('request'))

    def get_qr_data_uri(self, obj):
        from nht_sacco.apps.vehicles.services import ComplianceCardService
        return ComplianceCardService.get_qr_data_uri(obj, request=self.context.get('request'))


class DriverSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')
    portal_active = serializers.BooleanField(source='user.is_active', read_only=True, default=False)
    has_portal_account = serializers.SerializerMethodField()
    dl_days_remaining = serializers.SerializerMethodField()
    is_dl_expired = serializers.SerializerMethodField()
    current_assignment = serializers.SerializerMethodField()
    current_vehicle = serializers.SerializerMethodField()
    current_vehicle_plate = serializers.SerializerMethodField()

    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    create_portal_account = serializers.BooleanField(write_only=True, required=False, default=False)
    portal_username = serializers.CharField(write_only=True, required=False, allow_blank=True)
    portal_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    must_change_password = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'username', 'portal_active', 'has_portal_account',
            'create_portal_account', 'portal_username', 'portal_password', 'must_change_password',
            'full_name', 'national_id', 'phone_number', 'email',
            'driving_license_number', 'dl_class', 'dl_issue_date', 'dl_expiry_date',
            'dl_days_remaining', 'is_dl_expired',
            'psv_badge_number', 'psv_badge_expiry',
            'emergency_contact_name', 'emergency_contact_phone',
            'status', 'status_display',
            'vehicle', 'current_assignment', 'current_vehicle', 'current_vehicle_plate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        else:
            data = dict(data)
        if 'allocated_vehicle' in data and 'vehicle' not in data:
            data['vehicle'] = data.pop('allocated_vehicle')
        for key in ('vehicle', 'dl_issue_date', 'psv_badge_expiry'):
            if data.get(key) == '':
                data[key] = None
        return super().to_internal_value(data)

    def validate_driving_license_number(self, value):
        return (value or '').strip().upper()

    def validate_dl_class(self, value):
        return (value or '').strip().upper()

    def validate(self, attrs):
        dl_issue = attrs.get('dl_issue_date', getattr(self.instance, 'dl_issue_date', None))
        dl_expiry = attrs.get('dl_expiry_date', getattr(self.instance, 'dl_expiry_date', None))
        if dl_issue and dl_expiry and dl_expiry < dl_issue:
            raise serializers.ValidationError({
                'dl_expiry_date': 'Driving license expiry date cannot be earlier than the issue date.'
            })
        return attrs

    def get_has_portal_account(self, obj):
        return bool(obj.user_id and obj.user.is_active and obj.user.has_usable_password())

    def get_dl_days_remaining(self, obj):
        if not obj.dl_expiry_date:
            return None
        return (obj.dl_expiry_date - timezone.localdate()).days

    def get_is_dl_expired(self, obj):
        if not obj.dl_expiry_date:
            return False
        return obj.dl_expiry_date < timezone.localdate()

    def _get_active_assignment(self, obj):
        for assignment in obj.assignments.all():
            if assignment.is_current:
                return assignment
        return None

    def get_current_assignment(self, obj):
        assignment = self._get_active_assignment(obj)
        if not assignment or not assignment.vehicle_id:
            return None
        v = assignment.vehicle
        return {
            'id': str(assignment.pk),
            'vehicle_id': str(v.pk),
            'vehicle_plate': v.registration_number,
            'make_model': f"{v.make} {v.model}",
            'category_display': v.get_category_display(),
            'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        }

    def get_current_vehicle(self, obj):
        assignment = self._get_active_assignment(obj)
        return str(assignment.vehicle_id) if assignment and assignment.vehicle_id else None

    def get_current_vehicle_plate(self, obj):
        assignment = self._get_active_assignment(obj)
        return assignment.vehicle.registration_number if assignment and assignment.vehicle_id else ''


class DriverAssignmentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    driver_dl_number = serializers.CharField(source='driver.driving_license_number', read_only=True)
    driver_status = serializers.CharField(source='driver.status', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)
    vehicle_make_model = serializers.SerializerMethodField()

    class Meta:
        model = DriverAssignment
        fields = [
            'id', 'driver', 'driver_name', 'driver_dl_number', 'driver_status',
            'vehicle', 'vehicle_plate', 'vehicle_make_model',
            'assigned_at', 'relieved_at', 'is_current',
        ]

    def get_vehicle_make_model(self, obj):
        if not obj.vehicle_id:
            return ''
        return f"{obj.vehicle.make} {obj.vehicle.model}"


class RouteSerializer(serializers.ModelSerializer):
    active_vehicle_count = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = ['id', 'route_code', 'name', 'origin', 'destination', 'distance_km', 'intermediate_stops', 'is_active', 'active_vehicle_count']

    def get_active_vehicle_count(self, obj):
        return obj.allocated_vehicles.filter(is_active=True).count()


class VehicleRouteAssignmentSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)
    route_name = serializers.CharField(source='route.name', read_only=True)
    route_code = serializers.CharField(source='route.route_code', read_only=True)

    class Meta:
        model = VehicleRouteAssignment
        fields = ['id', 'vehicle', 'vehicle_plate', 'route', 'route_code', 'route_name', 'road_service_license', 'assigned_date', 'is_active']


class DocumentTypeSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = DocumentType
        fields = ['id', 'name', 'category', 'category_display', 'standard_validity_months', 'reminder_thresholds', 'is_mandatory_for_vehicle', 'is_mandatory_for_driver']


class DocumentSerializer(serializers.ModelSerializer):
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True, default='')
    driver_name = serializers.CharField(source='driver.full_name', read_only=True, default='')
    member_name = serializers.CharField(source='member.full_name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_expired = serializers.ReadOnlyField()
    days_to_expiry = serializers.ReadOnlyField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'document_type', 'document_type_name', 'vehicle', 'vehicle_plate',
            'member', 'member_name', 'driver', 'driver_name', 'reference_number',
            'issue_date', 'expiry_date', 'file', 'file_hash', 'version',
            'status', 'status_display', 'is_expired', 'days_to_expiry',
            'verification_notes', 'download_url', 'created_at',
        ]
        read_only_fields = ['id', 'file_hash', 'version', 'status', 'verification_notes', 'created_at']

    def get_download_url(self, obj):
        return f"/documents/{obj.pk}/download/"


class ComplianceAlertSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)
    alert_type_display = serializers.CharField(source='get_alert_type_display', read_only=True)

    class Meta:
        model = ComplianceAlert
        fields = ['id', 'vehicle', 'vehicle_plate', 'document', 'alert_type', 'alert_type_display', 'days_remaining', 'message', 'is_resolved', 'created_at', 'resolved_at']


class RenewalRequestSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)
    document_type_name = serializers.CharField(source='document_type.name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, default='')
    invoice_status = serializers.CharField(source='invoice.status', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = RenewalRequest
        fields = [
            'id', 'request_number', 'member', 'member_name', 'vehicle', 'vehicle_plate',
            'document_type', 'document_type_name', 'current_document', 'replacement_document',
            'invoice', 'invoice_number', 'invoice_status', 'status', 'status_display',
            'notes', 'assigned_officer', 'created_at', 'updated_at', 'completed_at',
        ]
        read_only_fields = ['id', 'request_number', 'status', 'assigned_officer', 'invoice', 'created_at', 'updated_at', 'completed_at']


class ServiceItemSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    default_amount = serializers.SerializerMethodField()

    class Meta:
        model = ServiceItem
        fields = ['id', 'code', 'name', 'category', 'category_display', 'default_amount', 'is_statutory', 'description', 'is_active']

    def get_default_amount(self, obj):
        tier = obj.price_tiers.order_by('-effective_from').first()
        return str(tier.amount) if tier else '0.00'


class InvoiceItemSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service_item.name', read_only=True)
    is_statutory = serializers.BooleanField(source='service_item.is_statutory', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ['id', 'service_item', 'service_name', 'is_statutory', 'description', 'unit_price', 'quantity', 'total_price']
        read_only_fields = ['id', 'total_price']


class InvoiceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    membership_number = serializers.CharField(source='member.membership_number', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    balance_due = serializers.ReadOnlyField()
    is_fully_paid = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    line_items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'member', 'member_name', 'membership_number',
            'vehicle', 'vehicle_plate', 'issue_date', 'due_date',
            'subtotal', 'statutory_total', 'total_amount', 'amount_paid', 'balance_due',
            'is_fully_paid', 'is_overdue', 'status', 'status_display', 'notes',
            'line_items', 'created_at',
        ]
        read_only_fields = ['id', 'invoice_number', 'subtotal', 'statutory_total', 'total_amount', 'amount_paid', 'created_at']


class PaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    receipt_id = serializers.UUIDField(source='receipt.id', read_only=True, default=None)
    receipt_number = serializers.CharField(source='receipt.receipt_number', read_only=True, default='')

    class Meta:
        model = Payment
        fields = [
            'id', 'payment_reference', 'invoice', 'invoice_number', 'member', 'member_name',
            'method', 'method_display', 'amount', 'currency', 'provider_transaction_id',
            'status', 'status_display', 'phone_number', 'receipt_id', 'receipt_number',
            'created_at', 'confirmed_at',
        ]


class ReceiptSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source='payment.payment_reference', read_only=True)
    provider_transaction_id = serializers.CharField(source='payment.provider_transaction_id', read_only=True)
    invoice_number = serializers.CharField(source='payment.invoice.invoice_number', read_only=True)
    member_name = serializers.CharField(source='payment.member.full_name', read_only=True)
    amount = serializers.DecimalField(source='payment.amount', max_digits=12, decimal_places=2, read_only=True)
    method_display = serializers.CharField(source='payment.get_method_display', read_only=True)
    print_url = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = ['id', 'receipt_number', 'payment_reference', 'provider_transaction_id', 'invoice_number', 'member_name', 'amount', 'method_display', 'issued_at', 'print_url']

    def get_print_url(self, obj):
        return f"/payments/receipts/{obj.pk}/"


class ManualPaymentVoucherSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.full_name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True)
    entered_by_username = serializers.CharField(source='entered_by.username', read_only=True)
    verified_by_username = serializers.CharField(source='verified_by.username', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ManualPaymentVoucher
        fields = [
            'id', 'invoice', 'invoice_number', 'member', 'member_name', 'method',
            'bank_slip_reference', 'bank_name', 'amount', 'payment_date',
            'entered_by', 'entered_by_username', 'verified_by', 'verified_by_username',
            'status', 'status_display', 'verification_notes', 'created_at', 'verified_at',
        ]
        read_only_fields = ['id', 'member', 'entered_by', 'verified_by', 'status', 'verification_notes', 'created_at', 'verified_at']


class ReconciliationExceptionSerializer(serializers.ModelSerializer):
    payment_reference = serializers.CharField(source='payment.payment_reference', read_only=True, default='')
    invoice_number = serializers.CharField(source='invoice.invoice_number', read_only=True, default='')
    exception_type_display = serializers.CharField(source='get_exception_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ReconciliationException
        fields = [
            'id', 'run', 'payment', 'payment_reference', 'invoice', 'invoice_number',
            'exception_type', 'exception_type_display', 'severity', 'description',
            'status', 'status_display', 'resolution_notes', 'resolved_at', 'created_at',
        ]


class ReconciliationRunSerializer(serializers.ModelSerializer):
    executed_by_username = serializers.CharField(source='executed_by.username', read_only=True, default='SYSTEM')
    exceptions = ReconciliationExceptionSerializer(many=True, read_only=True)

    class Meta:
        model = ReconciliationRun
        fields = [
            'id', 'run_reference', 'executed_by_username', 'period_start', 'period_end',
            'total_payments_checked', 'matched_count', 'exception_count',
            'total_matched_amount', 'notes', 'created_at', 'exceptions',
        ]


class AccountSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    current_balance = serializers.ReadOnlyField()

    class Meta:
        model = Account
        fields = ['id', 'code', 'name', 'type', 'type_display', 'description', 'is_active', 'current_balance']


class FinancialPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialPeriod
        fields = ['id', 'name', 'start_date', 'end_date', 'is_closed', 'created_at']


class JournalLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalLine
        fields = ['id', 'account', 'account_code', 'account_name', 'debit', 'credit']


class JournalEntrySerializer(serializers.ModelSerializer):
    period_name = serializers.CharField(source='period.name', read_only=True)
    posted_by_username = serializers.CharField(source='posted_by.username', read_only=True, default='SYSTEM')
    lines = JournalLineSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'date', 'period', 'period_name', 'reference',
            'narration', 'posted_by_username', 'is_posted', 'is_reversal',
            'reverses_entry', 'lines', 'created_at',
        ]


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    payment_account_name = serializers.CharField(source='payment_account.name', read_only=True)
    recorded_by_username = serializers.CharField(source='recorded_by.username', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.username', read_only=True, default='')

    class Meta:
        model = Expense
        fields = [
            'id', 'expense_number', 'category', 'category_name',
            'payment_account', 'payment_account_name', 'amount', 'date',
            'payee', 'description', 'recorded_by', 'recorded_by_username',
            'approved_by', 'approved_by_username', 'status', 'journal_entry',
            'created_at', 'approved_at',
        ]
        read_only_fields = ['id', 'expense_number', 'recorded_by', 'approved_by', 'status', 'journal_entry', 'created_at', 'approved_at']


class MaintenanceProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaintenanceProvider
        fields = ['id', 'name', 'contact_person', 'phone_number', 'email', 'physical_address', 'is_approved', 'specialty']


class SparePartSerializer(serializers.ModelSerializer):
    class Meta:
        model = SparePart
        fields = ['id', 'name', 'part_number', 'category', 'unit_cost', 'quantity_in_stock', 'minimum_reorder_level']


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)
    provider_name = serializers.CharField(source='provider.name', read_only=True, default='')
    type_display = serializers.CharField(source='get_maintenance_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MaintenanceRecord
        fields = [
            'id', 'work_order_number', 'vehicle', 'vehicle_plate', 'provider', 'provider_name',
            'maintenance_type', 'type_display', 'status', 'status_display',
            'scheduled_date', 'completed_date', 'odometer_reading', 'downtime_hours',
            'parts_cost', 'labour_cost', 'total_cost', 'description', 'technician_notes', 'created_at',
        ]
        read_only_fields = ['id', 'work_order_number', 'total_cost', 'created_at']


class IncidentUpdateSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True, default='SYSTEM')

    class Meta:
        model = IncidentUpdate
        fields = ['id', 'author_username', 'notes', 'status_change', 'created_at']


class IncidentSerializer(serializers.ModelSerializer):
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True, default='')
    member_name = serializers.CharField(source='reported_by_member.full_name', read_only=True, default='')
    assigned_officer_username = serializers.CharField(source='assigned_officer.username', read_only=True, default='')
    updates = IncidentUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = Incident
        fields = [
            'id', 'ticket_number', 'incident_type', 'severity', 'status',
            'reported_by_member', 'member_name', 'vehicle', 'vehicle_plate', 'driver',
            'title', 'description', 'location', 'date_occurred', 'resolution_notes',
            'assigned_officer', 'assigned_officer_username', 'resolved_at', 'updates', 'created_at',
        ]
        read_only_fields = ['id', 'ticket_number', 'resolved_at', 'created_at']


class CommitteeSerializer(serializers.ModelSerializer):
    chairperson_name = serializers.CharField(source='chairperson.get_full_name', read_only=True, default='')
    secretary_name = serializers.CharField(source='secretary.get_full_name', read_only=True, default='')

    class Meta:
        model = Committee
        fields = ['id', 'name', 'committee_type', 'description', 'term_years', 'is_active', 'chairperson', 'chairperson_name', 'secretary', 'secretary_name']


class MeetingSerializer(serializers.ModelSerializer):
    committee_name = serializers.CharField(source='committee.name', read_only=True)

    class Meta:
        model = Meeting
        fields = ['id', 'meeting_number', 'committee', 'committee_name', 'title', 'scheduled_date', 'location', 'status', 'quorum_reached', 'minutes_text']
        read_only_fields = ['id', 'meeting_number']


class ResolutionSerializer(serializers.ModelSerializer):
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)

    class Meta:
        model = Resolution
        fields = ['id', 'resolution_number', 'meeting', 'meeting_title', 'title', 'description', 'votes_for', 'votes_against', 'votes_abstained', 'status', 'effective_date']
        read_only_fields = ['id', 'resolution_number']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'code', 'name', 'channel', 'channel_display',
            'subject', 'body_template', 'meta_template_name',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'channel', 'category', 'title', 'message', 'status', 'created_at', 'read_at']


class CommunicationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunicationPreference
        fields = ['sms_enabled', 'whatsapp_enabled', 'email_enabled', 'in_app_enabled', 'compliance_alerts', 'billing_alerts', 'renewal_alerts', 'announcements']


class AnnouncementSerializer(serializers.ModelSerializer):
    published_by_username = serializers.CharField(source='published_by.username', read_only=True, default='SYSTEM')

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'content', 'priority', 'is_published', 'published_by_username', 'created_at']
        read_only_fields = ['id', 'published_by_username', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'actor_username', 'action', 'entity_type', 'entity_id', 'ip_address', 'outcome', 'change_details', 'timestamp']
