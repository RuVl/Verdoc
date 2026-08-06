from django.contrib.admin.apps import AdminConfig


class VerdocAdminConfig(AdminConfig):
    """Points django.contrib.admin at our AdminSite; listed in INSTALLED_APPS in its place."""

    default_site = "backend.admin.VerdocAdminSite"
