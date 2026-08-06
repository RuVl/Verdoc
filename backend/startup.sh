#!/bin/bash

# collect static files
uv run python manage.py collectstatic --no-input

# compile the .po catalogues (.mo files are build output, not tracked)
uv run python manage.py compilemessages --ignore=.venv

# run cron tasks
service cron start

# execute command from args
exec "$@"