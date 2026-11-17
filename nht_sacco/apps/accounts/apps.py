from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nht_sacco.apps.accounts'
    verbose_name = 'Accounts & Authentication'

    def ready(self):
        import nht_sacco.apps.accounts.signals
