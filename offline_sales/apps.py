# offline_sales/apps.py

from django.apps import AppConfig

class OfflineSalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'offline_sales'
    verbose_name = 'Offline Sales Management'

    def ready(self):
        import offline_sales.signals