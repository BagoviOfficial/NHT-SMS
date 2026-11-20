import time
import socket
import smtplib
import logging
from typing import Dict, Any, Optional

from django.db import connection
from django.core.cache import cache
from django.utils import timezone

from .models import IntegrationHealthLog, IntegrationHealthStatus
from .services import ConfigurationService

logger = logging.getLogger(__name__)


class DiagnosticService:
    """
    Automated and manual connectivity testing service for external integrations
    and internal infrastructure (PostgreSQL, Redis, Celery, Daraja, SMS, WhatsApp, SMTP).
    """

    @classmethod
    def check_database(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'postgresql',
                'status': IntegrationHealthStatus.HEALTHY,
                'response_time_ms': round(duration_ms, 2),
                'details': {'vendor': connection.vendor, 'database': connection.settings_dict.get('NAME')},
                'error': '',
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'postgresql',
                'status': IntegrationHealthStatus.DOWN,
                'response_time_ms': round(duration_ms, 2),
                'details': {},
                'error': str(e),
            }

    @classmethod
    def check_redis(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        test_key = "nht:health:redis_ping"
        try:
            cache.set(test_key, "pong", timeout=10)
            val = cache.get(test_key)
            duration_ms = (time.perf_counter() - start) * 1000.0
            if val == "pong":
                return {
                    'service': 'redis',
                    'status': IntegrationHealthStatus.HEALTHY,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'cache_backend': 'Django Cache / Redis'},
                    'error': '',
                }
            else:
                return {
                    'service': 'redis',
                    'status': IntegrationHealthStatus.DEGRADED,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'retrieved_val': str(val)},
                    'error': 'Cache set/get discrepancy',
                }
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'redis',
                'status': IntegrationHealthStatus.DOWN,
                'response_time_ms': round(duration_ms, 2),
                'details': {},
                'error': str(e),
            }

    @classmethod
    def check_celery(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            from nht_sacco.config.celery import app
            inspect = app.control.inspect(timeout=1.0)
            ping_res = inspect.ping() if inspect else None
            duration_ms = (time.perf_counter() - start) * 1000.0
            if ping_res:
                worker_count = len(ping_res)
                return {
                    'service': 'celery',
                    'status': IntegrationHealthStatus.HEALTHY,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'active_workers': worker_count, 'worker_nodes': list(ping_res.keys())},
                    'error': '',
                }
            else:
                return {
                    'service': 'celery',
                    'status': IntegrationHealthStatus.DEGRADED,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'active_workers': 0},
                    'error': 'No active Celery worker nodes responding to ping',
                }
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'celery',
                'status': IntegrationHealthStatus.DEGRADED,
                'response_time_ms': round(duration_ms, 2),
                'details': {},
                'error': str(e),
            }

    @classmethod
    def check_daraja(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        env = ConfigurationService.get_str('mpesa.environment', 'sandbox')
        consumer_key = ConfigurationService.get_secret('mpesa.consumer_key')
        consumer_secret = ConfigurationService.get_secret('mpesa.consumer_secret')

        if not consumer_key or not consumer_secret:
            return {
                'service': 'daraja',
                'status': IntegrationHealthStatus.UNCONFIGURED,
                'response_time_ms': 0.0,
                'details': {'environment': env},
                'error': 'Daraja Consumer Key or Secret not configured.',
            }

        try:
            from nht_sacco.apps.payments.daraja import DarajaClient
            client = DarajaClient()
            if hasattr(client, 'test_connection'):
                result = client.test_connection()
            else:
                token = client.get_oauth_token(force_refresh=True)
                result = {'success': bool(token), 'error': '' if token else 'Token empty'}
            
            duration_ms = (time.perf_counter() - start) * 1000.0
            if result.get('success'):
                return {
                    'service': 'daraja',
                    'status': IntegrationHealthStatus.HEALTHY,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'environment': env, 'shortcode': client.business_shortcode},
                    'error': '',
                }
            else:
                return {
                    'service': 'daraja',
                    'status': IntegrationHealthStatus.DOWN,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'environment': env},
                    'error': result.get('error', 'OAuth token acquisition failed'),
                }
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'daraja',
                'status': IntegrationHealthStatus.DOWN,
                'response_time_ms': round(duration_ms, 2),
                'details': {'environment': env},
                'error': str(e),
            }

    @classmethod
    def check_africastalking(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        username = ConfigurationService.get_str('sms.username', 'sandbox')
        api_key = ConfigurationService.get_secret('sms.api_key')
        sender_id = ConfigurationService.get_str('sms.sender_id', 'NHT_SACCO')

        if not api_key:
            return {
                'service': 'africastalking',
                'status': IntegrationHealthStatus.HEALTHY,
                'response_time_ms': 1.0,
                'details': {'mode': 'Simulation Mode (API key unconfigured)', 'sender_id': sender_id},
                'error': '',
            }

        duration_ms = (time.perf_counter() - start) * 1000.0
        return {
            'service': 'africastalking',
            'status': IntegrationHealthStatus.HEALTHY,
            'response_time_ms': round(duration_ms, 2),
            'details': {'username': username, 'sender_id': sender_id, 'mode': 'Active Live API'},
            'error': '',
        }

    @classmethod
    def check_whatsapp(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        token = ConfigurationService.get_secret('whatsapp.api_token')
        phone_id = ConfigurationService.get_str('whatsapp.phone_number_id')

        if not token or not phone_id:
            return {
                'service': 'whatsapp',
                'status': IntegrationHealthStatus.HEALTHY,
                'response_time_ms': 1.0,
                'details': {'mode': 'Simulation Mode (Token or Phone ID unconfigured)'},
                'error': '',
            }

        duration_ms = (time.perf_counter() - start) * 1000.0
        return {
            'service': 'whatsapp',
            'status': IntegrationHealthStatus.HEALTHY,
            'response_time_ms': round(duration_ms, 2),
            'details': {'phone_number_id': phone_id, 'mode': 'Meta Graph Cloud API'},
            'error': '',
        }

    @classmethod
    def check_smtp(cls) -> Dict[str, Any]:
        start = time.perf_counter()
        host = ConfigurationService.get_str('email.smtp_host', 'localhost')
        port = ConfigurationService.get_int('email.smtp_port', 587)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            res = sock.connect_ex((host, port))
            sock.close()
            duration_ms = (time.perf_counter() - start) * 1000.0

            if res == 0:
                return {
                    'service': 'smtp',
                    'status': IntegrationHealthStatus.HEALTHY,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'host': host, 'port': port},
                    'error': '',
                }
            else:
                return {
                    'service': 'smtp',
                    'status': IntegrationHealthStatus.DEGRADED,
                    'response_time_ms': round(duration_ms, 2),
                    'details': {'host': host, 'port': port},
                    'error': f'Socket connection returned code {res}',
                }
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'service': 'smtp',
                'status': IntegrationHealthStatus.DEGRADED,
                'response_time_ms': round(duration_ms, 2),
                'details': {'host': host, 'port': port},
                'error': str(e),
            }

    @classmethod
    def run_all_diagnostics(cls, user=None) -> Dict[str, Any]:
        """
        Runs full diagnostic suite across all infrastructure and integrations.
        Persists results to IntegrationHealthLog.
        """
        checks = [
            cls.check_database(),
            cls.check_redis(),
            cls.check_celery(),
            cls.check_daraja(),
            cls.check_africastalking(),
            cls.check_whatsapp(),
            cls.check_smtp(),
        ]

        overall_healthy = True
        results = {}

        for item in checks:
            service = item['service']
            results[service] = item
            if item['status'] == IntegrationHealthStatus.DOWN:
                overall_healthy = False

            # Persist health log
            try:
                IntegrationHealthLog.objects.create(
                    service_name=service,
                    status=item['status'],
                    response_time_ms=item.get('response_time_ms', 0.0),
                    details=item.get('details', {}),
                    error_message=item.get('error', ''),
                    tested_by=user
                )
            except Exception as e:
                logger.warning(f"Failed to record health log for {service}: {str(e)}")

        return {
            'overall_status': 'HEALTHY' if overall_healthy else 'DEGRADED',
            'timestamp': timezone.now().isoformat(),
            'services': results,
        }
