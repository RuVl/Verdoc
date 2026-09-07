"""Absolute URLs, built the same way everywhere."""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest


def absolute_url(path: str, request: HttpRequest | None = None) -> str:
    """
    Turn a path into a link that survives leaving the site.

    Every link we hand out - the purchases page, one file, the unsubscribe page - is opened from an
    inbox, so it has to carry the host. Which host is the question this answers, see current_site().
    The scheme is a setting so a local run can hand out http:// links that actually open.
    """

    return f"{settings.SITE_SCHEME}://{current_site(request).domain}{path}"


def current_site(request: HttpRequest | None = None) -> Site:
    """
    The site a link belongs to.

    With a request (and no SITE_ID, which is production) `get_current` reads the host off it - that
    is how the mirror domain keeps mailing links to itself. Without one - cron, the Plisio webhook -
    Django does not fall back to the django_site table: `get_current(None)` with no SITE_ID raises
    ImproperlyConfigured. So pick the site by DEFAULT_SITE_DOMAIN instead. SITE_ID, when it is set
    (local development), still wins and decides on its own.
    """

    if request is not None or getattr(settings, "SITE_ID", ""):
        return Site.objects.get_current(request)

    domain = settings.DEFAULT_SITE_DOMAIN

    try:
        return Site.objects.get(domain=domain)
    except Site.DoesNotExist:
        raise ImproperlyConfigured(
            f"No site with domain {domain!r} (DEFAULT_SITE_DOMAIN). Links built without a request "
            f"have no host to read, so that row has to exist: add it under Sites in the admin, or "
            f"point DEFAULT_SITE_DOMAIN at a domain that is already there."
        ) from None
