from multiprocessing import cpu_count
from os import environ

bind = '0.0.0.0:' + environ.get('PORT', '8000')
max_requests = 1000

worker_class = 'gevent'
workers = cpu_count()

env = {
    'DJANGO_SETTINGS_MODULE': 'backend.settings'
}

reload = True
name = 'backend'
