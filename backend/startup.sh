#!/bin/bash

# collect static files
uv run python manage.py collectstatic --no-input

# run cron tasks
service cron start

# execute command from args
exec "$@"