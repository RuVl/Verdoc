"""Absolute URLs, built the same way everywhere."""

from django.conf import settings
from django.contrib.sites.models import Site
from django.http import HttpRequest


def absolute_url(path: str, request: HttpRequest | None = None) -> str:
    """
    Turn a path into a link that survives leaving the site.

    Every link we hand out - the purchases page, one file, the unsubscribe page - is opened from an
    inbox, so it has to carry the host. Which host is the question this answers: with no SITE_ID
    set, `get_current(request)` reads it off the request, which is how the mirror domain keeps
    mailing links to itself; from the Plisio webhook or from cron there is no request and the
    django_site row decides. The scheme is a setting so a local run can hand out http:// links
    that actually open.
    """

    return f"{settings.SITE_SCHEME}://{Site.objects.get_current(request).domain}{path}"
