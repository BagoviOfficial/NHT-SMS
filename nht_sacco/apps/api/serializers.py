from decimal import Decimal
from rest_framework import serializers

from nht_sacco.apps.accounts.models import User, UserRole, LoginHistory
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.vehicles.models import Vehicle, VehicleOwnershipHistory
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
            'is_active',
            'is_verified',
            'is_staff',
            'must_change_password',
            'last_login',
            'last_login_ip',
            'date_joined',
            'password',
        ]
        read_only_fields = ['id', 'is_staff', 'last_login', 'last_login_ip', 'date_joined']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

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
    full_name = serializers.ReadOnlyField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = Member
        fields = [
            'id', 'user', 'username', 'membership_number', 'first_name', 'middle_name', 'last_name',
            'full_name', 'national_id', 'phone_number', 'email', 'postal_address', 'county',
            'category', 'category_display', 'status', 'status_display',
            'next_of_kin_name', 'next_of_kin_relation', 'next_of_kin_phone',
            'application_date', 'approval_date', 'approval_notes', 'created_at',
        ]
        read_only_fields = ['id', 'membership_number', 'application_date', 'approval_date', 'created_at']


class VehicleSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='current_owner.full_name', read_only=True)
    owner_membership_no = serializers.CharField(source='current_owner.membership_number', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    compliance_status = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'registration_number', 'chassis_number', 'engine_number', 'make', 'model',
            'year_of_manufacture', 'category', 'category_display', 'fuel_type',
            'carrying_capacity', 'color', 'current_owner', 'owner_name', 'owner_membership_no',
            'status', 'status_display', 'qr_token', 'compliance_status', 'registered_at',
        ]
        read_only_fields = ['id', 'qr_token', 'registered_at']

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


class DriverSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True, default='')

    class Meta:
        model = Driver
        fields = [
            'id', 'user', 'username', 'full_name', 'national_id', 'phone_number',
            'driving_license_number', 'dl_expiry_date', 'psv_badge_number', 'psv_badge_expiry',
            'emergency_contact_name', 'emergency_contact_phone', 'status', 'status_display', 'created_at',
        ]


class DriverAssignmentSerializer(serializers.ModelSerializer):
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.registration_number', read_only=True)

    class Meta:
        model = DriverAssignment
        fields = ['id', 'driver', 'driver_name', 'vehicle', 'vehicle_plate', 'assigned_at', 'relieved_at', 'is_current']


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
