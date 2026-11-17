from django.urls import path
from . import views

app_name = 'vehicles'

urlpatterns = [
    path('verify/<uuid:qr_token>/', views.VehicleQRVerificationView.as_view(), name='vehicle_qr_verify'),
    path('<uuid:qr_token>/', views.VehicleQRVerificationView.as_view(), name='vehicle_qr_direct'),
]
