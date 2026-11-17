from django.views.generic import DetailView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Vehicle
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.compliance.models import ComplianceStatus

class VehicleQRVerificationView(DetailView):
    """
    Public QR Verification Endpoint for Road Inspection Officers and Commuters.
    Exposes only essential fleet regulatory status with strict Zero-PII protection.
    """
    model = Vehicle
    template_name = 'vehicles/public_verification.html'
    slug_field = 'qr_token'
    slug_url_kwarg = 'qr_token'
    context_object_name = 'vehicle'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        vehicle = self.object
        compliance = ComplianceService.get_vehicle_compliance_status(vehicle)

        ctx['compliance'] = compliance
        ctx['is_fully_compliant'] = compliance['status'] == ComplianceStatus.FULLY_COMPLIANT
        ctx['verification_timestamp'] = timezone.now()
        ctx['title'] = f"Fleet Verification - {vehicle.registration_number}"
        return ctx
