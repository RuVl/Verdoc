import multiprocessing

import environ
import gevent.monkey

gevent.monkey.patch_all()
env = environ.Env(
    GUNICORN_WORKERS=(int, multiprocessing.cpu_count() * 2 + 1),
)

# Основные настройки
bind = "0.0.0.0:" + env.str("PORT", "8000")
workers = env.int("GUNICORN_WORKERS")
worker_class = env.str("GUNICORN_WORKER_CLASS", "gevent")
worker_connections = env.int("GUNICORN_WORKER_CONNECTIONS", 1000)
max_requests = env.int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = env.int("GUNICORN_MAX_REQUESTS_JITTER", 100)
timeout = env.int("GUNICORN_TIMEOUT", 30)
keepalive = env.int("GUNICORN_KEEPALIVE", 2)

# Настройки процесса
preload_app = True
daemon = False  # bcs Docker
tmp_upload_dir = "/tmp"

# Безопасность
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Логирование
loglevel = env.str("GUNICORN_LOG_LEVEL", "INFO").upper()
capture_output = True  # Перехватывает stdout/stderr Django приложения

# Формат access логов (работает с logconfig_dict)
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s %(p)s'

# Детальный формат логов
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "generic": {
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter",
        },
        "access": {
            "format": "%(message)s",  # bcs access_log_format is set
            "class": "logging.Formatter",
        },
    },
    "handlers": {  # ОБЯЗАТЕЛЬНО определить console и error_console!
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stdout",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stderr",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "generic",
            "filename": "./logs/gunicorn-error.log",
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "access",
            "filename": "./logs/gunicorn-access.log",
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "gunicorn.error": {
            "handlers": ["error_console", "error_file"],
            "level": loglevel,
            "propagate": False,
        },
        "gunicorn.access": {
            "handlers": ["console", "access_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
