from django.apps import AppConfig


class PassportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'passport'

    def ready(self):
        # noinspection PyUnresolvedReferences
        import passport.signals  # Implicitly connect signal handlers decorated with @receiver
