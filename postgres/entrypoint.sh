#!/bin/bash
set -euo pipefail

# Cron jobs run with a stripped environment, so the container env is not visible
# to backup.sh. Persist the vars it needs and let the script source them.
ENV_FILE=/etc/postgres-backup.env
: >"$ENV_FILE"
chmod 600 "$ENV_FILE"
for var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD DOCKER_POSTGRES_HOST DOCKER_POSTGRES_PORT; do
  printf 'export %s=%q\n' "$var" "${!var-}" >>"$ENV_FILE"
done

service cron start

# Hand over to the stock entrypoint - postgres stays the direct child of PID 1
# (catatonit/tini via `init: true`), so it never reaps cron as its own child.
exec docker-entrypoint.sh "$@"
