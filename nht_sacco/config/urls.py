"""
Root URL Configuration for NHT-SMS.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView
from nht_sacco.apps.vehicles.views import VehicleQRVerificationView
from nht_sacco.apps.payments.views import MPesaCallbackView

def health_live(request):
    """Liveness probe: verifies application process is running."""
    return JsonResponse({'status': 'alive', 'service': 'NHT-SMS'}, status=200)

def health_ready(request):
    """Readiness probe: verifies database connectivity."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        db_status = 'connected'
        status_code = 200
    except Exception as e:
        db_status = f'error: {str(e)}'
        status_code = 503

    return JsonResponse({
        'status': 'ready' if status_code == 200 else 'degraded',
        'database': db_status,
        'service': 'NHT-SMS',
    }, status=status_code)

urlpatterns = [
    # Health checks
    path('health/live/', health_live, name='health-live'),
    path('health/ready/', health_ready, name='health-ready'),

    # Admin portal
    path('admin/', admin.site.urls),

    # Authentication & User Accounts
    path('accounts/', include('nht_sacco.apps.accounts.urls', namespace='accounts')),

    # Documents & Private Storage Vault
    path('documents/', include('nht_sacco.apps.documents.urls', namespace='documents')),

    # Fleet & Public QR Verification
    path('vehicles/', include('nht_sacco.apps.vehicles.urls', namespace='vehicles')),
    path('verify/vehicle/<uuid:qr_token>/', VehicleQRVerificationView.as_view(), name='vehicle_public_verify'),

    # Billing & Financial Payments
    path('billing/', include('nht_sacco.apps.billing.urls', namespace='billing')),
    path('payments/', include('nht_sacco.apps.payments.urls', namespace='payments')),
    path('accounting/', include('nht_sacco.apps.accounting.urls', namespace='accounting')),
    path('renewals/', include('nht_sacco.apps.renewals.urls', namespace='renewals')),
    path('api/v1/payments/mpesa/callback/', MPesaCallbackView.as_view(), name='api_mpesa_callback'),

    # Member Self-Service Portal
    path('portal/', include('nht_sacco.apps.members.portal_urls', namespace='portal')),

    # Executive Reporting & Analytics
    path('reports/', include('nht_sacco.apps.reports.urls', namespace='reports')),

    # Root redirect to accounts login
    path('', RedirectView.as_view(pattern_name='accounts:login', permanent=False), name='root-home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
