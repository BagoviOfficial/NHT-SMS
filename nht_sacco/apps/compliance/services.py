from datetime import date
from django.utils import timezone
from nht_sacco.apps.vehicles.models import Vehicle, VehicleStatus
from nht_sacco.apps.documents.models import Document, DocumentType, VerificationStatus
from .models import ComplianceStatus, ComplianceAlert

class ComplianceService:
    @staticmethod
    def get_vehicle_compliance_status(vehicle):
        """
        Calculates the complete regulatory compliance profile for a vehicle.
        Checks all mandatory document types against active, verified documents.
        """
        today = timezone.now().date()
        mandatory_types = DocumentType.objects.filter(is_mandatory_for_vehicle=True)

        missing_mandatory = []
        expired_docs = []
        expiring_soon_docs = []
        valid_docs = []

        for doc_type in mandatory_types:
            # Find the latest verified document for this vehicle and type
            doc = Document.objects.filter(
                vehicle=vehicle,
                document_type=doc_type,
                status=VerificationStatus.VERIFIED
            ).order_by('-expiry_date', '-version').first()

            if not doc:
                missing_mandatory.append(doc_type)
            elif doc.expiry_date < today:
                expired_docs.append(doc)
            elif (doc.expiry_date - today).days <= 14:
                expiring_soon_docs.append(doc)
            else:
                valid_docs.append(doc)

        # Determine overall status
        if missing_mandatory or expired_docs:
            overall_status = ComplianceStatus.NON_COMPLIANT
        elif expiring_soon_docs:
            overall_status = ComplianceStatus.EXPIRING_SOON
        else:
            overall_status = ComplianceStatus.FULLY_COMPLIANT

        return {
            'status': overall_status,
            'missing_mandatory': missing_mandatory,
            'expired_docs': expired_docs,
            'expiring_soon_docs': expiring_soon_docs,
            'valid_docs': valid_docs,
            'checked_at': timezone.now(),
        }

    check_vehicle_compliance = get_vehicle_compliance_status

    @classmethod
    def run_daily_compliance_scan(cls):
        """
        Automated compliance scan identifying expiring or expired regulatory documents.
        Generates ComplianceAlert entries based on reminder thresholds [30, 14, 7, 3, 0].
        """
        today = timezone.now().date()
        active_vehicles = Vehicle.objects.filter(status=VehicleStatus.ACTIVE)
        
        alerts_created = 0
        non_compliant_count = 0

        for vehicle in active_vehicles:
            compliance = cls.get_vehicle_compliance_status(vehicle)
            if compliance['status'] == ComplianceStatus.NON_COMPLIANT:
                non_compliant_count += 1

            # Check expired documents
            for doc in compliance['expired_docs']:
                days_overdue = (today - doc.expiry_date).days
                # Prevent duplicate alerts for today
                exists = ComplianceAlert.objects.filter(
                    vehicle=vehicle,
                    document=doc,
                    alert_type=ComplianceAlert.AlertType.EXPIRED,
                    created_at__date=today
                ).exists()
                if not exists:
                    ComplianceAlert.objects.create(
                        vehicle=vehicle,
                        document=doc,
                        alert_type=ComplianceAlert.AlertType.EXPIRED,
                        days_remaining=-days_overdue,
                        message=f"{doc.document_type.name} expired {days_overdue} days ago on {doc.expiry_date}.",
                        recipient_member=vehicle.current_owner
                    )
                    alerts_created += 1

            # Check upcoming expiry thresholds
            for doc in compliance['expiring_soon_docs']:
                days_left = (doc.expiry_date - today).days
                thresholds = doc.document_type.reminder_thresholds or [30, 14, 7, 3, 0]
                if days_left in thresholds:
                    exists = ComplianceAlert.objects.filter(
                        vehicle=vehicle,
                        document=doc,
                        alert_type=ComplianceAlert.AlertType.UPCOMING_EXPIRY,
                        days_remaining=days_left,
                        created_at__date=today
                    ).exists()
                    if not exists:
                        ComplianceAlert.objects.create(
                            vehicle=vehicle,
                            document=doc,
                            alert_type=ComplianceAlert.AlertType.UPCOMING_EXPIRY,
                            days_remaining=days_left,
                            message=f"{doc.document_type.name} expires in {days_left} days (on {doc.expiry_date}).",
                            recipient_member=vehicle.current_owner
                        )
                        alerts_created += 1

                        if vehicle.current_owner:
                            try:
                                from nht_sacco.apps.notifications.services import NotificationDispatcherService
                                from nht_sacco.apps.notifications.models import NotificationCategory
                                NotificationDispatcherService.dispatch_to_member(
                                    member=vehicle.current_owner,
                                    category=NotificationCategory.COMPLIANCE,
                                    title=f"Compliance Alert: {vehicle.registration_number}",
                                    message=f"Permit {doc.document_type.name} for vehicle {vehicle.registration_number} expires in {days_left} days (on {doc.expiry_date}).",
                                    template_code="COMPLIANCE_EXPIRING_30D_SMS",
                                    context={
                                        'member_name': vehicle.current_owner.full_name,
                                        'vehicle_plate': vehicle.registration_number,
                                        'doc_type': doc.document_type.name,
                                        'expiry_date': str(doc.expiry_date),
                                    }
                                )
                            except Exception:
                                pass

            # Check missing mandatory documents
            for missing_type in compliance['missing_mandatory']:
                exists = ComplianceAlert.objects.filter(
                    vehicle=vehicle,
                    alert_type=ComplianceAlert.AlertType.MISSING_DOCUMENT,
                    message__contains=missing_type.name,
                    is_resolved=False
                ).exists()
                if not exists:
                    ComplianceAlert.objects.create(
                        vehicle=vehicle,
                        document=None,
                        alert_type=ComplianceAlert.AlertType.MISSING_DOCUMENT,
                        days_remaining=0,
                        message=f"Mandatory regulatory requirement '{missing_type.name}' has not been uploaded or verified.",
                        recipient_member=vehicle.current_owner
                    )
                    alerts_created += 1

        return {
            'total_vehicles_scanned': active_vehicles.count(),
            'non_compliant_count': non_compliant_count,
            'alerts_created': alerts_created,
            'scan_date': today,
        }
