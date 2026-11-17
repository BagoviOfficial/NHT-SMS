"""
NHT-SMS Package Configuration.
Northern Highways Transporters SACCO Management System.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
