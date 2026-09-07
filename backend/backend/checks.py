"""Deploy-time checks for the settings a link depends on."""

from django.conf import settings
from django.core.checks import Error, Tags, register

# Tags.database, so this runs on `migrate` - a deploy step - rather than on every management
# command. The point is to fail the deploy, not to make `makemigrations` talk to the database.


@register(Tags.database)
def default_site_domain_has_a_row(app_configs, databases=None, **kwargs):
    """
    Every off-request link is built from the django_site row named by DEFAULT_SITE_DOMAIN.

    Without the row the broadcast sender raises once per recipient, and each raise is swallowed
    into a FAILED delivery - the failure mode this check exists to move forward into the deploy.
    """

    if not databases or getattr(settings, "SITE_ID", ""):
        return []

    domain = getattr(settings, "DEFAULT_SITE_DOMAIN", "")
    if not domain:
        return [
            Error(
                "DEFAULT_SITE_DOMAIN is empty, so links built without a request have no host.",
                hint="Set DEFAULT_SITE_DOMAIN, or make the first ALLOWED_HOSTS entry the main domain.",
                id="backend.E001",
            )
        ]

    from django.contrib.sites.models import Site
    from django.db import DatabaseError

    try:
        # The connection `migrate` is running against, not whatever happens to be default.
        exists = Site.objects.using(databases[0]).filter(domain=domain).exists()
    except DatabaseError:
        # No table yet (the very first migrate), or the database is not reachable - migrate itself
        # is about to say so far more clearly than this check could.
        return []

    if exists:
        return []

    return [
        Error(
            f"No django_site row has the domain {domain!r} (DEFAULT_SITE_DOMAIN).",
            hint="Add it under Sites in the admin, or point DEFAULT_SITE_DOMAIN at a domain that is there.",
            id="backend.E002",
        )
    ]
