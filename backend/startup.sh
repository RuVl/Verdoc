#!/bin/bash

# collect static files
python3 manage.py collectstatic --no-input

# run cron tasks
service cron start

# execute command from args
exec "$@"