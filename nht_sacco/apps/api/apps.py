from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nht_sacco.apps.api'
    verbose_name = 'Unified REST API & SPA Shell'
