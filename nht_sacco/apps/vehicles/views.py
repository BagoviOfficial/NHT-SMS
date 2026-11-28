from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.views import View

from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.integrations.models import CompanyProfile
from nht_sacco.config.mui import render_mui_app
from .models import Vehicle
from .services import ComplianceCardService


def _apply_no_cache_verify_headers(resp):
    add_never_cache_headers(resp)
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp['X-Robots-Tag'] = 'noindex, nofollow'
    return resp


class VehicleQRVerificationView(View):
    """
    Legacy Public QR Verification Endpoint for Vehicle UUID QR tokens.
    Exposes only essential fleet regulatory status with strict Zero-PII protection
    inside the unified Material UI shell.
    """
    def get(self, request, qr_token, *args, **kwargs):
        vehicle = get_object_or_404(Vehicle, qr_token=qr_token)
        compliance = ComplianceService.get_vehicle_compliance_status(vehicle)
        profile = CompanyProfile.get_active()
        sacco_logo_url = '/settings/api/v1/company-profile/logo-asset/' if (profile.logo and profile.logo.name) else ''

        outcome = 'VALID' if compliance['status'] == ComplianceStatus.FULLY_COMPLIANT else (
            'EXPIRED' if compliance['expired_docs'] else 'SUSPENDED'
        )
        if vehicle.status != 'ACTIVE':
            outcome = 'SUSPENDED'

        verified_at = timezone.now()
        verify_result = {
            'outcome': outcome,
            'is_valid': outcome == 'VALID' or compliance['status'] == ComplianceStatus.EXPIRING_SOON,
            'headline': 'Fully Compliant' if compliance['status'] == ComplianceStatus.FULLY_COMPLIANT else (
                'Expiring Soon' if compliance['status'] == ComplianceStatus.EXPIRING_SOON else 'Non-Compliant'
            ),
            'detail': 'Verified live against SACCO fleet regulatory registry.',
            'sacco_name': profile.trading_name,
            'sacco_legal_name': profile.legal_name,
            'sacco_logo_url': sacco_logo_url,
            'verified_at': verified_at.isoformat(),
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
        resp = render_mui_app(
            request,
            initial_route='public-verify',
            page_title=f"Fleet Verification - {vehicle.registration_number}",
            page_data={'verify_result': verify_result},
        )
        return _apply_no_cache_verify_headers(resp)


class ComplianceCardPublicVerifyView(View):
    """
    Public HTTPS Compliance Card Verification Endpoint (/verify/compliance/<token>/).
    Zero-PII, IP rate-limited, no-store caching, rendered via the single MUI shell.
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
            return _apply_no_cache_verify_headers(resp)
        try:
            if cache.get(rate_key) is None:
                cache.set(rate_key, 1, self.RATE_LIMIT_WINDOW_SECONDS)
            else:
                cache.incr(rate_key)
        except Exception:
            cache.set(rate_key, hits + 1, self.RATE_LIMIT_WINDOW_SECONDS)

        result = ComplianceCardService.evaluate_live_status(token)
        status_code = 200 if result['outcome'] != 'INVALID' else 404
        resp = render_mui_app(
            request,
            initial_route='public-verify',
            page_title=f"Compliance Verification - {result['outcome']}",
            page_data={'verify_result': result},
            status=status_code,
        )
        return _apply_no_cache_verify_headers(resp)
