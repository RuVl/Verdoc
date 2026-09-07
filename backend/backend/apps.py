from django.contrib.admin.apps import AdminConfig


class VerdocAdminConfig(AdminConfig):
    """Points django.contrib.admin at our AdminSite; listed in INSTALLED_APPS in its place."""

    default_site = "backend.admin.VerdocAdminSite"

    def ready(self):
        super().ready()

        # Registers the deploy-time check that DEFAULT_SITE_DOMAIN names a real site row.
        from backend import checks  # noqa: F401
