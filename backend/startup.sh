#!/bin/bash

# collect static files
uv run python manage.py collectstatic --no-input

# compile the .po catalogues (.mo files are build output, not tracked)
uv run python manage.py compilemessages --ignore=.venv

# Debian cron wipes the environment, and settings.py reads os.environ - the vars from the compose
# env_file never reach the jobs, so every one of them died on SECRET_KEY. Dump the whole environment
# for the jobs to source (see cronjob). compgen -e rather than a list of names: a setting added
# later must not silently break the mailing months from now.
CRON_ENV_FILE=/etc/verdoc-cron.env
: >"$CRON_ENV_FILE"
chmod 600 "$CRON_ENV_FILE"
for var in $(compgen -e); do
  printf 'export %s=%q\n' "$var" "${!var}" >>"$CRON_ENV_FILE"
done

# run cron tasks
service cron start

# execute command from args
exec "$@"