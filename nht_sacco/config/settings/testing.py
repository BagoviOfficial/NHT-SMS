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

# In-memory email backend
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Disable rate limiting during automated test suites
AXES_ENABLED = False
