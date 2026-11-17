"""
Celery background tasks for SACCO compliance monitoring.
"""

import logging
from nht_sacco.apps.compliance.services import ComplianceService

logger = logging.getLogger(__name__)


def task_daily_compliance_scan():
    """
    Automated daily task that evaluates the regulatory compliance status of all
    active vehicles and drivers, generating alerts and triggering notifications.
    """
    logger.info("Starting daily regulatory compliance scan...")
    result = ComplianceService.run_daily_compliance_scan()
    logger.info("Compliance scan completed: %s", result)
    return result


try:
    from celery import shared_task
    task_daily_compliance_scan = shared_task(name='nht_sacco.apps.compliance.tasks.task_daily_compliance_scan')(task_daily_compliance_scan)
except ImportError:
    pass
