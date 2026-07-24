from django.apps import AppConfig


class PassportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "passport"

    def ready(self):
        # Import signals so the @receiver handlers get connected.
        from . import signals  # noqa: F401
