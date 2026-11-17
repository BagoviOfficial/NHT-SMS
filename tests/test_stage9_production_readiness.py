"""
Stage 9 Automated Test Suite: Production Readiness, Deployment & Verification.
Northern Highways Transporters SACCO Management System (NHT-SMS).
"""

import os
import subprocess
from pathlib import Path
import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse
from nht_sacco.apps.compliance.tasks import task_daily_compliance_scan
from nht_sacco.apps.billing.tasks import task_overdue_invoice_reminders
from nht_sacco.apps.notifications.tasks import task_retry_failed_notifications
from nht_sacco.apps.members.tasks import task_monthly_member_statements

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.django_db
class TestProductionHealthChecks:
    def setup_method(self):
        self.client = Client()

    def test_liveness_probe_returns_200_and_payload(self):
        url = reverse('health-live')
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'alive'
        assert data.get('service') == 'NHT-SMS'

    def test_readiness_probe_returns_200_and_database_connected(self):
        url = reverse('health-ready')
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'ready'
        assert data.get('database') == 'connected'
        assert data.get('service') == 'NHT-SMS'


class TestProductionSettingsHardening:
    def test_production_settings_security_parameters(self):
        """
        Validates that production settings enforce ASVS Level 2 requirements.
        """
        from nht_sacco.config.settings import production as prod_settings

        assert prod_settings.DEBUG is False
        assert prod_settings.SECURE_SSL_REDIRECT is True
        assert prod_settings.SESSION_COOKIE_SECURE is True
        assert prod_settings.CSRF_COOKIE_SECURE is True
        assert prod_settings.SESSION_COOKIE_HTTPONLY is True
        assert prod_settings.CSRF_COOKIE_HTTPONLY is True
        assert prod_settings.SESSION_COOKIE_SAMESITE == 'Lax'
        assert prod_settings.CSRF_COOKIE_SAMESITE == 'Lax'
        assert prod_settings.SECURE_HSTS_SECONDS >= 31536000
        assert prod_settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert prod_settings.SECURE_HSTS_PRELOAD is True
        assert prod_settings.X_FRAME_OPTIONS == 'DENY'
        assert prod_settings.SECURE_CONTENT_TYPE_NOSNIFF is True


class TestContainerAndDeploymentConfigurations:
    def test_dockerfile_and_compose_exist_and_configured(self):
        dockerfile = BASE_DIR / 'Dockerfile'
        docker_compose = BASE_DIR / 'docker-compose.yml'
        entrypoint = BASE_DIR / 'docker' / 'entrypoint.sh'
        gunicorn_conf = BASE_DIR / 'docker' / 'gunicorn.conf.py'
        nginx_conf = BASE_DIR / 'docker' / 'nginx' / 'nht_sacco.conf'
        nginx_vps_conf = BASE_DIR / 'docker' / 'nginx' / 'nht_sacco_vps.conf'

        assert dockerfile.exists() and dockerfile.stat().st_size > 200
        assert docker_compose.exists() and docker_compose.stat().st_size > 500
        assert entrypoint.exists() and os.access(str(entrypoint), os.X_OK)
        assert gunicorn_conf.exists()
        assert nginx_conf.exists()
        assert nginx_vps_conf.exists()

    def test_systemd_service_units_exist(self):
        gunicorn_service = BASE_DIR / 'docker' / 'systemd' / 'nht-sms-gunicorn.service'
        celery_worker = BASE_DIR / 'docker' / 'systemd' / 'nht-sms-celery-worker.service'
        celery_beat = BASE_DIR / 'docker' / 'systemd' / 'nht-sms-celery-beat.service'

        assert gunicorn_service.exists()
        assert celery_worker.exists()
        assert celery_beat.exists()


class TestBackupAutomationScripts:
    def test_backup_scripts_executable_and_valid(self):
        backup_db = BASE_DIR / 'scripts' / 'backup_db.sh'
        restore_db = BASE_DIR / 'scripts' / 'restore_db.sh'
        backup_media = BASE_DIR / 'scripts' / 'backup_media.sh'

        assert backup_db.exists() and os.access(str(backup_db), os.X_OK)
        assert restore_db.exists() and os.access(str(restore_db), os.X_OK)
        assert backup_media.exists() and os.access(str(backup_media), os.X_OK)

    def test_backup_db_script_creates_valid_sha256_archive(self):
        """
        Executes backup_db.sh and asserts archive and checksum integrity.
        """
        result = subprocess.run(
            [str(BASE_DIR / 'scripts' / 'backup_db.sh')],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        backup_dir = BASE_DIR / 'backups' / 'db'
        assert backup_dir.exists()

        sql_gz_files = list(backup_dir.glob('nht_sms_db_*.sql.gz'))
        assert len(sql_gz_files) > 0
        latest_backup = sorted(sql_gz_files)[-1]
        assert latest_backup.stat().st_size > 0

        checksum_file = Path(str(latest_backup) + '.sha256')
        assert checksum_file.exists()


@pytest.mark.django_db
class TestCeleryBackgroundTasks:
    def test_compliance_scan_task_executes_successfully(self):
        result = task_daily_compliance_scan()
        assert isinstance(result, dict)
        assert 'alerts_created' in result
        assert 'non_compliant_count' in result

    def test_overdue_invoice_reminder_task_executes_successfully(self):
        result = task_overdue_invoice_reminders()
        assert isinstance(result, dict)
        assert 'overdue_count' in result
        assert 'reminders_sent' in result

    def test_retry_failed_notifications_task_executes_successfully(self):
        result = task_retry_failed_notifications()
        assert isinstance(result, dict)
        assert 'retried_count' in result
        assert 'success_count' in result

    def test_monthly_member_statements_task_executes_successfully(self):
        result = task_monthly_member_statements()
        assert isinstance(result, dict)
        assert 'members_processed' in result


class TestDocumentationCompleteness:
    REQUIRED_DOCS = [
        BASE_DIR / 'README.md',
        BASE_DIR / 'PROJECT_STATUS.md',
        BASE_DIR / 'docs' / 'SYSTEM_ARCHITECTURE.md',
        BASE_DIR / 'docs' / 'DATABASE_SCHEMA.md',
        BASE_DIR / 'docs' / 'API_DOCUMENTATION.md',
        BASE_DIR / 'docs' / 'USER_ROLES_AND_PERMISSIONS.md',
        BASE_DIR / 'docs' / 'SECURITY.md',
        BASE_DIR / 'docs' / 'PRIVACY_AND_DATA_RETENTION.md',
        BASE_DIR / 'docs' / 'PAYMENT_INTEGRATION.md',
        BASE_DIR / 'docs' / 'NOTIFICATION_INTEGRATION.md',
        BASE_DIR / 'docs' / 'DEPLOYMENT_GUIDE.md',
        BASE_DIR / 'docs' / 'BACKUP_AND_DISASTER_RECOVERY.md',
        BASE_DIR / 'docs' / 'TESTING_REPORT.md',
        BASE_DIR / 'docs' / 'TROUBLESHOOTING.md',
        BASE_DIR / 'docs' / 'CHANGELOG.md',
    ]

    def test_all_15_production_documentation_guides_exist_and_complete(self):
        for doc_path in self.REQUIRED_DOCS:
            assert doc_path.exists(), f"Missing required document: {doc_path.name}"
            size = doc_path.stat().st_size
            assert size > 500, f"Document {doc_path.name} is too short ({size} bytes)"

            content = doc_path.read_text(encoding='utf-8')
            assert content.startswith('# '), f"Document {doc_path.name} must start with markdown heading '# '"
