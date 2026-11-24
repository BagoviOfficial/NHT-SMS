"""
Django settings for NHT-SMS (Northern Highways Transporters SACCO Management System).
Base settings shared across all environments.
"""

from pathlib import Path
import sys
import environ

# Paths:
# BASE_DIR is the workspace root (/.../NHT-SMS)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'nht_sacco'))

# Initialize environment parser
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'django-insecure-default-change-me-immediately-in-production'),
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost']),
    DATABASE_URL=(str, 'postgresql://u0_a366:@localhost:5432/nht_sms_db'),
    PRIVATE_MEDIA_ROOT=(str, str(BASE_DIR / 'media' / 'private')),
    EMAIL_BACKEND=(str, 'django.core.mail.backends.console.EmailBackend'),
)

# Read .env file if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'axes',
    'django_otp',
    'django_otp.plugins.otp_totp',
]

LOCAL_APPS = [
    'nht_sacco.apps.accounts',
    'nht_sacco.apps.audit',
    'nht_sacco.apps.members',
    'nht_sacco.apps.vehicles',
    'nht_sacco.apps.drivers',
    'nht_sacco.apps.routes',
    'nht_sacco.apps.compliance',
    'nht_sacco.apps.documents',
    'nht_sacco.apps.renewals',
    'nht_sacco.apps.billing',
    'nht_sacco.apps.payments',
    'nht_sacco.apps.accounting',
    'nht_sacco.apps.notifications',
    'nht_sacco.apps.maintenance',
    'nht_sacco.apps.incidents',
    'nht_sacco.apps.governance',
    'nht_sacco.apps.reports',
    'nht_sacco.apps.integrations',
    'nht_sacco.apps.api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'nht_sacco.apps.accounts.middleware.SessionSecurityMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'nht_sacco.apps.audit.middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'nht_sacco.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'nht_sacco.apps.accounts.context_processors.brand_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'nht_sacco.config.wsgi.application'
ASGI_APPLICATION = 'nht_sacco.config.asgi.application'

# Database
# Default: PostgreSQL
DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgresql://u0_a366:@localhost:5432/nht_sms_db'
    )
}

# Authentication backends (Axes rate-limiting + Django ModelBackend)
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization & Currency
LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True
DEFAULT_CURRENCY = 'KES'

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media' / 'public'
PRIVATE_MEDIA_ROOT = Path(env('PRIVATE_MEDIA_ROOT'))

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# Session Security Settings
SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE', 43200)  # 12 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_IDLE_TIMEOUT_STAFF_SECONDS = env.int('SESSION_IDLE_TIMEOUT_STAFF_SECONDS', 1800)  # 30 minutes
SESSION_IDLE_TIMEOUT_MEMBER_SECONDS = env.int('SESSION_IDLE_TIMEOUT_MEMBER_SECONDS', 43200) # 12 hours

# Django Axes Security Configuration
AXES_FAILURE_LIMIT = env.int('AXES_FAILURE_LIMIT', 5)
AXES_COOLOFF_TIME = env.int('AXES_COOLOFF_TIME', 1)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'accounts/lockout.html'
AXES_VERBOSE = True

# Email Configuration
EMAIL_BACKEND = env('EMAIL_BACKEND')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'nht_sacco': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'axes': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ==============================================================================
# Celery & Background Automation Configuration
# ==============================================================================
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max execution

# Celery Beat Periodic Task Schedules
CELERY_BEAT_SCHEDULE = {
    'compliance-daily-scan': {
        'task': 'nht_sacco.apps.compliance.tasks.task_daily_compliance_scan',
        'schedule': 86400.0,  # Run daily
    },
    'invoice-overdue-reminders': {
        'task': 'nht_sacco.apps.billing.tasks.task_overdue_invoice_reminders',
        'schedule': 86400.0,  # Run daily
    },
    'notifications-retry-failed': {
        'task': 'nht_sacco.apps.notifications.tasks.task_retry_failed_notifications',
        'schedule': 1800.0,   # Run every 30 minutes
    },
    'members-monthly-statements': {
        'task': 'nht_sacco.apps.members.tasks.task_monthly_member_statements',
        'schedule': 2592000.0, # Run monthly
    },
}

# ==============================================================================
# Safaricom Daraja M-Pesa Integration Settings
# ==============================================================================
MPESA_ENVIRONMENT = env('MPESA_ENVIRONMENT', default='sandbox')
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY', default='sandbox_key')
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET', default='sandbox_secret')
MPESA_BUSINESS_SHORTCODE = env('MPESA_BUSINESS_SHORTCODE', default='174379')
MPESA_PASSKEY = env('MPESA_PASSKEY', default='bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919')
MPESA_CALLBACK_URL = env('MPESA_CALLBACK_URL', default='https://example.com/api/v1/payments/mpesa/callback/')
MPESA_CALLBACK_TOKEN = env('MPESA_CALLBACK_TOKEN', default='nht-mpesa-token-secret')

# ==============================================================================
# Africa's Talking SMS Settings (Harmonized)
# ==============================================================================
AT_ENVIRONMENT = env('AT_ENVIRONMENT', default='sandbox')
AFRICASTALKING_USERNAME = env('AT_USERNAME', default=env('AFRICASTALKING_USERNAME', default='sandbox'))
AFRICASTALKING_API_KEY = env('AT_API_KEY', default=env('AFRICASTALKING_API_KEY', default=''))
AFRICASTALKING_SENDER_ID = env('AT_SENDER_ID', default=env('AFRICASTALKING_SENDER_ID', default='NHT_SACCO'))

# ==============================================================================
# Meta WhatsApp Cloud API Integration Settings
# ==============================================================================
WHATSAPP_ENVIRONMENT = env('WHATSAPP_ENVIRONMENT', default='sandbox')
WHATSAPP_API_TOKEN = env('WHATSAPP_API_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = env('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = env('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')
WHATSAPP_WEBHOOK_VERIFY_TOKEN = env('WHATSAPP_WEBHOOK_VERIFY_TOKEN', default='')
NOTIFICATION_SIMULATION_MODE = env.bool('NOTIFICATION_SIMULATION_MODE', default=True)

# Cryptographic Key Management Settings
SETTINGS_ENCRYPTION_KEY = env('SETTINGS_ENCRYPTION_KEY', default=None)
SETTINGS_ENCRYPTION_KEY_FILE = env('SETTINGS_ENCRYPTION_KEY_FILE', default=None)
SETTINGS_ENCRYPTION_KEY_FALLBACKS = env.list('SETTINGS_ENCRYPTION_KEY_FALLBACKS', default=[])



