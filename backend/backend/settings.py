from pathlib import Path

import environ


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),  # set casting, default value
)
# environ.Env.read_env(BASE_DIR / 'dev.env')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
CORS_ORIGIN_ALLOW_ALL = True  # WARNING! Do not use this in production!
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:5173",
# ]

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

# Application definition
INSTALLED_APPS = [
    'modeltranslation',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'djmoney',
    'djmoney.contrib.exchange',

    'passport'
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

# Database
DATABASES = {
    'default': env.db()
}

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

USE_TZ = True
TIME_ZONE = 'UTC'

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = []  # List of non-standard paths

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Currency
CURRENCIES = ('USD', 'RUB')
BASE_CURRENCY = 'USD'
EXCHANGE_BACKEND = 'djmoney.contrib.exchange.backends.OpenExchangeRatesBackend'
OPEN_EXCHANGE_RATES_APP_ID = env('OPENEXCHANGERATES_APP_ID')
# Schedule the task for update currencies
# https://channels.readthedocs.io/en/stable/topics/worker.html
