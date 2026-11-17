"""
WSGI config for NHT-SMS.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nht_sacco.config.settings.development')

application = get_wsgi_application()
