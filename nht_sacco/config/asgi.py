"""
ASGI config for NHT-SMS.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nht_sacco.config.settings.development')

application = get_asgi_application()
