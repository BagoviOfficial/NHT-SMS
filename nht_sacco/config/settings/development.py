"""
Development settings for NHT-SMS.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Console email backend for inspection
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Relax axes cooloff slightly during development for smooth testing
AXES_COOLOFF_TIME = 0.1
