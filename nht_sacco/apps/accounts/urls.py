from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication & Profile
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('lockout/', views.LockoutView.as_view(), name='lockout'),

    # Password Management
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Multi-Factor Authentication (MFA / TOTP)
    path('mfa/setup/', views.TOTPSetupView.as_view(), name='totp_setup'),
    path('mfa/verify/', views.TOTPVerifyView.as_view(), name='totp_verify'),
]
