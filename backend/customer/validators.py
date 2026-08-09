import logging

import dns.exception
import dns.resolver
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

DNS_TIMEOUT = 3  # seconds - the checkout request waits on this
MX_HIT_TTL = 60 * 60 * 24  # a domain gaining or losing mail is rare
MX_MISS_TTL = 60 * 60  # shorter, in case a fresh domain is still propagating


def _resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.timeout = DNS_TIMEOUT
    resolver.lifetime = DNS_TIMEOUT
    return resolver


def domain_accepts_mail(domain: str) -> bool:
    """
    Whether anything would accept mail for `domain`.

    Fails open on purpose: a DNS timeout or a broken resolver must never stop a customer from
    buying, so only a definitive "nowhere to deliver" answer counts as a rejection.
    """

    resolver = _resolver()
    try:
        resolver.resolve(domain, "MX")
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        # RFC 5321: with no MX record the A record is the mail exchanger.
        try:
            resolver.resolve(domain, "A")
            return True
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return False
        except dns.exception.DNSException as e:
            logger.warning(f"A lookup for {domain} failed, letting it through: {e}")
            return True
    except dns.exception.DNSException as e:
        logger.warning(f"MX lookup for {domain} failed, letting it through: {e}")
        return True


def validate_email_domain(email: str) -> None:
    """Reject an address whose domain cannot receive mail - a typo or a made-up domain."""

    if not settings.VALIDATE_EMAIL_MX:
        return

    domain = email.rpartition("@")[2].lower()
    if not domain:
        raise ValidationError("Enter a valid email address.", code="invalid")

    cache_key = f"mx-domain:{domain}"
    accepts = cache.get(cache_key)
    if accepts is None:
        accepts = domain_accepts_mail(domain)
        cache.set(cache_key, accepts, MX_HIT_TTL if accepts else MX_MISS_TTL)

    if not accepts:
        raise ValidationError(f"The domain {domain} cannot receive mail", code="undeliverable_domain")
