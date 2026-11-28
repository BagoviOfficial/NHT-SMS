"""
Testing settings for NHT-SMS.
"""

from .base import *

DEBUG = False
TESTING = True

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Fast in-memory SQLite for rapid automated test runs
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# In-memory email mailer
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
    }
}

# Disable rate limiting during automated test suites
AXES_ENABLED = False

# Dedicated testing encryption key
SETTINGS_ENCRYPTION_KEY = 'test-settings-encryption-key-for-nht-sms-automated-testing-32chars'
SETTINGS_ENCRYPTION_KEY_FILE = None
SETTINGS_ENCRYPTION_KEY_FALLBACKS = []
OTP_TOTP_THROTTLE_FACTOR = 0
