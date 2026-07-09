from django.apps import AppConfig

class EcomConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Ecom'
    
    def ready(self):
        import Ecom.signals  # Register signals