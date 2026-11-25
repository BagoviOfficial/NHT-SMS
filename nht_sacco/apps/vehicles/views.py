from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views import View
from django.views.generic import DetailView

from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.integrations.models import CompanyProfile
from .models import Vehicle
from .services import ComplianceCardService


class VehicleQRVerificationView(DetailView):
    """
    Legacy Public QR Verification Endpoint for Vehicle UUID QR tokens.
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
        profile = CompanyProfile.get_active()
        sacco_logo_url = '/settings/api/v1/company-profile/logo-asset/' if (profile.logo and profile.logo.name) else ''

        outcome = 'VALID' if compliance['status'] == ComplianceStatus.FULLY_COMPLIANT else (
            'EXPIRED' if compliance['expired_docs'] else 'SUSPENDED'
        )
        if vehicle.status != 'ACTIVE':
            outcome = 'SUSPENDED'

        ctx['compliance'] = compliance
        ctx['is_fully_compliant'] = compliance['status'] == ComplianceStatus.FULLY_COMPLIANT
        ctx['verification_timestamp'] = timezone.now()
        ctx['title'] = f"Fleet Verification - {vehicle.registration_number}"
        ctx['verify_result'] = {
            'outcome': outcome,
            'is_valid': outcome == 'VALID' or compliance['status'] == ComplianceStatus.EXPIRING_SOON,
            'headline': 'Fully Compliant' if compliance['status'] == ComplianceStatus.FULLY_COMPLIANT else (
                'Expiring Soon' if compliance['status'] == ComplianceStatus.EXPIRING_SOON else 'Non-Compliant'
            ),
            'detail': 'Verified live against SACCO fleet regulatory registry.',
            'sacco_name': profile.trading_name,
            'sacco_legal_name': profile.legal_name,
            'sacco_logo_url': sacco_logo_url,
            'verified_at': ctx['verification_timestamp'],
            'card': {
                'certificate_number': 'LEGACY-FLEET-QR',
                'registration_number': vehicle.registration_number,
                'make_model': f"{vehicle.make} {vehicle.model}",
                'category': vehicle.get_category_display(),
                'carrying_capacity': vehicle.carrying_capacity,
                'fleet_number': '',
                'assigned_route': '',
                'issue_date': None,
                'expiry_date': None,
                'vehicle_status': vehicle.get_status_display(),
            },
        }
        return ctx

    def render_to_response(self, context, **response_kwargs):
        resp = super().render_to_response(context, **response_kwargs)
        add_never_cache_headers(resp)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        return resp


class ComplianceCardPublicVerifyView(View):
    """
    Public HTTPS Compliance Card Verification Endpoint (/verify/compliance/<token>/).
    - Requires no login.
    - Enforces IP rate limiting against token enumeration.
    - Checks live database state (VALID, EXPIRED, REVOKED, SUSPENDED, SUPERSEDED, INVALID).
    - Disables HTTP caching (`Cache-Control: no-store`).
    - Exposes strictly zero PII.
    """
    RATE_LIMIT_MAX_REQUESTS = 60
    RATE_LIMIT_WINDOW_SECONDS = 60

    def get(self, request, token, *args, **kwargs):
        ip = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR') or 'unknown').split(',')[0].strip()
        rate_key = f"nht:qr_verify_rl:{ip}"
        hits = cache.get(rate_key, 0)
        if hits >= self.RATE_LIMIT_MAX_REQUESTS:
            resp = HttpResponse(
                "Too many verification requests. Please wait a minute before scanning again.",
                status=429,
                content_type='text/plain',
            )
            add_never_cache_headers(resp)
            resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            return resp
        try:
            if cache.get(rate_key) is None:
                cache.set(rate_key, 1, self.RATE_LIMIT_WINDOW_SECONDS)
            else:
                cache.incr(rate_key)
        except Exception:
            cache.set(rate_key, hits + 1, self.RATE_LIMIT_WINDOW_SECONDS)

        result = ComplianceCardService.evaluate_live_status(token)
        status_code = 200 if result['outcome'] != 'INVALID' else 404
        resp = render(
            request,
            'vehicles/public_verification.html',
            {
                'verify_result': result,
                'verification_timestamp': result['verified_at'],
                'title': f"Compliance Verification - {result['outcome']}",
            },
            status=status_code,
        )
        add_never_cache_headers(resp)
        resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp['X-Robots-Tag'] = 'noindex, nofollow'
        return resp
