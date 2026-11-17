"""
Celery background worker configuration for NHT-SMS.
Northern Highways Transporters SACCO Management System.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nht_sacco.config.settings.development')

try:
    from celery import Celery

    app = Celery('nht_sacco')

    # Using a string here means the worker doesn't have to serialize
    # the configuration object to child processes.
    app.config_from_object('django.conf:settings', namespace='CELERY')

    # Load task modules from all registered Django apps.
    app.autodiscover_tasks()

except ImportError:
    # Graceful degradation in environments where Celery is not installed
    logger.info("Celery is not installed in the local environment; running in synchronous compatibility mode.")
    app = None
