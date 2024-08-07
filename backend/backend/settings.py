from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

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
    'modeltranslation',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    'rest_framework',
    'corsheaders',

    'djmoney',
    'djmoney.contrib.exchange',

    'passport',
    'order'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Site settings
SITE_ID = 1
SITE_SCHEME = 'https'  # Uses to build absolute url

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

DATABASES = {
    'default': env.db()
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Custom serializers
SERIALIZATION_MODULES = {
    'json': 'djmoney.serializers'
}

# Internationalization
USE_I18N = True
USE_L10N = True
LANGUAGE_CODE = 'en-us'
LANGUAGES = (
    ('en', 'English'),
    ('ru', 'Russian')
)
MODELTRANSLATION_DEFAULT_LANGUAGE = 'en'

# Timezone
USE_TZ = True
TIME_ZONE = 'UTC'

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = []  # List of non-standard paths

# Currency settings
CURRENCIES = ('USD', 'RUB')
BASE_CURRENCY = 'USD'
EXCHANGE_BACKEND = 'djmoney.contrib.exchange.backends.OpenExchangeRatesBackend'
OPEN_EXCHANGE_RATES_APP_ID = env('OPENEXCHANGERATES_APP_ID')

# Plisio token
PLISIO_SECRET_KEY = env('PLISIO_SECRET_KEY')

# Email config
EMAIL_CONFIG = env.email()

EMAIL_HOST_USER = EMAIL_CONFIG.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = EMAIL_CONFIG.get('EMAIL_HOST_PASSWORD')

EMAIL_HOST = EMAIL_CONFIG.get('EMAIL_HOST')
EMAIL_PORT = EMAIL_CONFIG.get('EMAIL_PORT')

DEFAULT_FROM_EMAIL = env.get_value('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

EMAIL_BACKEND = EMAIL_CONFIG.get('EMAIL_BACKEND')
EMAIL_USE_TLS = EMAIL_CONFIG.get('EMAIL_USE_TLS', False)
EMAIL_USE_SSL = EMAIL_CONFIG.get('EMAIL_USE_SSL', False)
