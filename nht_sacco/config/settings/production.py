"""
Production settings for NHT-SMS on Ubuntu VPS.
Northern Highways Transporters SACCO Management System.
"""

import os
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

# In production, simulated notification mode is explicitly disabled
NOTIFICATION_SIMULATION_MODE = False

# Production Email Mailer (defaults to SMTP unless explicitly overridden)
MAILERS = {
    'default': build_mailer_config(
        os.getenv('EMAIL_BACKEND') or 'django.core.mail.backends.smtp.EmailBackend',
        env_parser=env,
    ),
}

# Security Headers & SSL Hardening
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Static files with WhiteNoise / Nginx (Django 6.x STORAGES)
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Daraja Production Configuration
MPESA_ENVIRONMENT = env('MPESA_ENVIRONMENT', default='live')


def validate_production_secrets():
    """
    Validates required production environment variables and security parameters at startup.
    Raises ImproperlyConfigured if any insecure fallback or missing credential is detected.
    """
    errors = []

    # 1. Secret Key Validation
    secret_key = env('SECRET_KEY', default='')
    if not secret_key:
        errors.append("SECRET_KEY is missing in production environment.")
    elif secret_key.startswith('django-insecure-') or 'change-me' in secret_key or len(secret_key) < 50:
        errors.append("Insecure SECRET_KEY detected: must be at least 50 characters and not use default placeholders.")

    # 2. Allowed Hosts Validation
    allowed_hosts = env.list('ALLOWED_HOSTS', default=[])
    if not allowed_hosts or '*' in allowed_hosts:
        errors.append("ALLOWED_HOSTS must be explicitly defined and cannot contain wildcard '*' in production.")

    # 3. Database URL Validation
    db_url = env('DATABASE_URL', default='')
    if not db_url:
        errors.append("DATABASE_URL is required in production environment.")
    elif 'postgresql://u0_a366:@localhost' in db_url:
        errors.append("DATABASE_URL cannot use local unauthenticated dev credentials in production.")

    # 4. Safaricom Daraja Credentials Validation
    mpesa_key = env('MPESA_CONSUMER_KEY', default='')
    mpesa_secret = env('MPESA_CONSUMER_SECRET', default='')
    mpesa_passkey = env('MPESA_PASSKEY', default='')
    mpesa_token = env('MPESA_CALLBACK_TOKEN', default='')
    sandbox_passkey = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'

    if not mpesa_key or mpesa_key == 'sandbox_key':
        errors.append("MPESA_CONSUMER_KEY is missing or using sandbox placeholder in production.")
    if not mpesa_secret or mpesa_secret == 'sandbox_secret':
        errors.append("MPESA_CONSUMER_SECRET is missing or using sandbox placeholder in production.")
    if not mpesa_passkey or mpesa_passkey == sandbox_passkey:
        errors.append("MPESA_PASSKEY is missing or using default Safaricom sandbox passkey in production.")
    if not mpesa_token or mpesa_token in ('nht-mpesa-token-secret', 'change-to-a-cryptographic-callback-token'):
        errors.append("MPESA_CALLBACK_TOKEN must be set to a strong cryptographic secret in production.")

    # 5. Configuration Encryption Key Independence
    enc_key = env('SETTINGS_ENCRYPTION_KEY', default='')
    if not enc_key:
        errors.append("SETTINGS_ENCRYPTION_KEY is required in production environment.")
    elif len(enc_key) < 32:
        errors.append("SETTINGS_ENCRYPTION_KEY must be at least 32 characters in length.")
    elif enc_key == secret_key:
        errors.append("SETTINGS_ENCRYPTION_KEY must be strictly independent and not identical to SECRET_KEY.")
    elif 'change-me' in enc_key or 'default' in enc_key:
        errors.append("Insecure SETTINGS_ENCRYPTION_KEY detected: cannot use development default placeholders.")

    if errors:
        error_msg = "[NHT-SMS PRODUCTION HARDENING AUDIT] FATAL STARTUP CONFIGURATION ERRORS:\n" + "\n".join(f" - {e}" for e in errors)
        raise ImproperlyConfigured(error_msg)


# Enforce startup validation when running under production settings
if os.getenv('DJANGO_SETTINGS_MODULE') == 'nht_sacco.config.settings.production' and not os.getenv('SKIP_PRODUCTION_SECRET_VALIDATION'):
    validate_production_secrets()
