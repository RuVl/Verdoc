from django.contrib import admin
from django.urls import path, reverse


class VerdocAdminSite(admin.AdminSite):
    """
    The default admin site plus the pages that are not a model list.

    It replaces `admin.site` through `VerdocAdminConfig.default_site`, so nothing else changes:
    `admin.site` is a lazy proxy that resolves to whatever the admin app config names, and every
    `@admin.register` in the project keeps writing to this instance.
    """

    site_header = "Verdoc"
    site_title = "Verdoc"

    def get_urls(self):
        # Imported here, not at module level: this module is loaded while the app registry is
        # still being populated, and the views pull in models.
        from sales.admin_views import statistics_csv_view, statistics_view

        return [
            path("stats/", self.admin_view(statistics_view), name="stats"),
            path("stats/export/", self.admin_view(statistics_csv_view), name="stats-export"),
        ] + super().get_urls()

    def get_app_list(self, request, app_label=None):
        """
        Put the statistics page in the sidebar and on the dashboard.

        Both are rendered from this list, and the base implementation builds it out of registered
        models alone - a bare URL would exist but be reachable only by typing it. Filtering by
        `app_label` is how the per-app pages ask, and statistics belong to no app, so they are
        left out of that call.
        """

        app_list = super().get_app_list(request, app_label)
        if app_label is not None or not request.user.is_staff:
            return app_list

        stats_url = reverse("admin:stats", current_app=self.name)
        statistics = {
            "name": "Statistics",
            "app_label": "statistics",
            "app_url": stats_url,
            "has_module_perms": True,
            "models": [
                {
                    "name": "Sales dashboard",
                    "object_name": "statistics",
                    "admin_url": stats_url,
                    "add_url": None,
                    "perms": {"view": True},
                    "view_only": True,
                }
            ],
        }
        return [statistics, *app_list]
