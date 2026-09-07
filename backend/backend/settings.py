from datetime import timedelta
from email.utils import parseaddr
from pathlib import Path

import environ
from django.core.mail.utils import DNS_NAME

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")

# Development settings
if DEBUG:
    # Local only. In production SITE_ID stays unset on purpose: one backend serves two domains and
    # `Site.objects.get_current(request)` then picks the site by Host header, which is how the
    # mirror keeps its links to itself. Links built without a request use DEFAULT_SITE_DOMAIN.
    SITE_ID = 1

# Production settings
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # from reverse proxy

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True  # Remember to add site to https://hstspreload.org/

# Application definition
INSTALLED_APPS = [
    "modeltranslation",
    # Stands in for "django.contrib.admin": same app, our AdminSite (see backend/admin.py).
    "backend.apps.VerdocAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "corsheaders",
    "djmoney",
    "djmoney.contrib.exchange",
    "tinymce",
    "catalog",
    "customer",
    "mailing",
    "sales",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"

# Site settings
# Used to build absolute URLs (download links, the purchases page link in e-mails).
# Overridable so a local run can hand out http:// links that actually open.
SITE_SCHEME = env("SITE_SCHEME", default="https")

# The domain links are signed with when there is no request to read the Host from - cron
# (broadcast), and anything else built off-request. With SITE_ID unset Django refuses to guess a
# site, so name the domain here. The first ALLOWED_HOSTS entry is already "the main domain"
# elsewhere (sales/views.py picks the Plisio key by it), so it is the default.
DEFAULT_SITE_DOMAIN = env("DEFAULT_SITE_DOMAIN", default=ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "")

# Customer access lifetimes
PURCHASES_PAGE_TTL = timedelta(hours=24)  # Customer.access_token
DOWNLOAD_TTL = timedelta(hours=24)  # Allocation.token

# Checkout limits. Every unpaid order holds its units until it expires, so one request must not be
# able to lock a whole product.
MAX_ITEM_QUANTITY = 30
MAX_ORDER_ITEMS = 25

# DRF ships BasicAuthentication on by default, which turns every public endpoint into a place to
# try Django passwords against. Nothing here authenticates over Basic - the admin uses a session -
# so the storefront API is left with the session alone.
# The browsable API renders a writable HTML form on every endpoint, so production speaks JSON only.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

if DEBUG:
    REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"].append("rest_framework.renderers.BrowsableAPIRenderer")

# Look up the MX record of the e-mail domain at checkout. Fails open on any DNS trouble, see
# customer/validators.py - turn it off only if outbound DNS is blocked.
VALIDATE_EMAIL_MX = env.bool("VALIDATE_EMAIL_MX", default=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "standard",
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security.DisallowedHost": {
            "handlers": ["null"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

DATABASES = {
    "default": env.db(),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Custom serializers
SERIALIZATION_MODULES = {
    "json": "djmoney.serializers",
}

# Internationalization
USE_I18N = True
LANGUAGE_CODE = "en"
LANGUAGES = (
    ("en", "English"),
    ("ru", "Russian"),
)
MODELTRANSLATION_DEFAULT_LANGUAGE = "en"

# gettext catalogues for the e-mail copy. msgids are the English text, so only `ru` has a
# catalogue here. `.mo` files are compiled by startup.sh and are not tracked.
LOCALE_PATHS = [BASE_DIR / "locale"]

# Timezone
USE_TZ = True
TIME_ZONE = "UTC"

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"

# Media files (the product files being sold).
#
# BASE_DIR, not BASE_DIR / "products": the stored names already carry that prefix
# (StockItem.file is upload_to="products/"), so the join lands on /app/products/<name> in the
# container - the products_volume mount - and on backend/products/<name> on a host run. Adding
# the directory here would double it and break every download.
#
# This is what the empty default already resolved to, since it is taken against the working
# directory and every way we start Django has cwd == BASE_DIR (WORKDIR /app in the image, `cd
# backend` in the Makefile). Spelling it out drops that coincidence: cron runs from the home
# directory, so a job that ever touches a file would have looked for it under /root.
#
# MEDIA_URL is spelled out at the value Django computes anyway ("" gets a script prefix added).
MEDIA_ROOT = BASE_DIR
MEDIA_URL = "/"

# Currency settings
CURRENCIES = ("USD", "RUB")
BASE_CURRENCY = "USD"
EXCHANGE_BACKEND = "djmoney.contrib.exchange.backends.OpenExchangeRatesBackend"
OPEN_EXCHANGE_RATES_APP_ID = env("OPENEXCHANGERATES_APP_ID")

# Plisio token
PLISIO_SECRET_KEY = env("PLISIO_SECRET_KEY")
MIRROR_PLISIO_SECRET_KEY = env("MIRROR_PLISIO_SECRET_KEY")

# Email config
# The backend follows the scheme of EMAIL_URL (smtp:// in production, consolemail:// in dev).
# Passing `backend=` here would pin it to SMTP and silently ignore the scheme.
EMAIL_CONFIG = env.email("EMAIL_URL")

EMAIL_HOST_USER = EMAIL_CONFIG.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = EMAIL_CONFIG.get("EMAIL_HOST_PASSWORD")

EMAIL_HOST = EMAIL_CONFIG.get("EMAIL_HOST")
EMAIL_PORT = EMAIL_CONFIG.get("EMAIL_PORT")

DEFAULT_FROM_EMAIL = env.get_value("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)

# Django stamps Message-ID and the SMTP EHLO greeting with socket.getfqdn(), which leaks the machine
# or container hostname into every delivered message and leaves a Message-ID whose domain does not
# match From:. Pin it to the sender domain - that is also the DKIM domain, so the two cannot drift.
# parseaddr survives a "Name <a@b>" sender; a value with no domain in it falls back rather than
# stamping the placeholder itself.
EMAIL_FQDN = env.get_value(
    "EMAIL_FQDN", default=parseaddr(DEFAULT_FROM_EMAIL or "")[1].partition("@")[2] or "localhost"
)
DNS_NAME._fqdn = EMAIL_FQDN

EMAIL_BACKEND = EMAIL_CONFIG.get("EMAIL_BACKEND")
EMAIL_USE_TLS = EMAIL_CONFIG.get("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = EMAIL_CONFIG.get("EMAIL_USE_SSL", False)

# TinyMCE (self-hosted GPL build, no API key) - WYSIWYG editor for Broadcast.body in admin.
# promotion/branding False strip the "Upgrade" button and "Powered by Tiny" ads.
# skin/content_css default to light; a capture-phase script in the broadcast change_form
# swaps them to the dark variants when the admin theme is dark (see change_form.html).
TINYMCE_DEFAULT_CONFIG = {
    "height": 500,
    "menubar": "edit insert format table",
    "promotion": False,
    "branding": False,
    "skin": "oxide",
    "content_css": "default",
    "plugins": "advlist autolink lists link image charmap preview anchor "
    "searchreplace visualblocks code fullscreen insertdatetime table help wordcount",
    "toolbar": "undo redo | blocks | bold italic forecolor | "
    "alignleft aligncenter alignright | bullist numlist | "
    "link image table | removeformat | preview code fullscreen | help",
}
