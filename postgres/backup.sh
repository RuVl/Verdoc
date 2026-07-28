#!/bin/bash

# Settings
BACKUP_DIR=/var/backups/postgres
DATE=$(date +\%Y-\%m-\%d_\%H-\%M-\%S)
FILENAME=backup_$DATE.dump

# Cron strips the environment - the entrypoint saved the vars here
ENV_FILE=/etc/postgres-backup.env
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

# Password for postgres utilities
export PGPASSWORD="$POSTGRES_PASSWORD"

# Make dirs if not exist
mkdir -p $BACKUP_DIR

# Backup database - dump to a temp file so a failed run leaves no empty .dump
if pg_dump -U "$POSTGRES_USER" -h "$DOCKER_POSTGRES_HOST" -p "$DOCKER_POSTGRES_PORT" \
        -F c -f "$BACKUP_DIR/$FILENAME.tmp" "$POSTGRES_DB"; then
    mv "$BACKUP_DIR/$FILENAME.tmp" "$BACKUP_DIR/$FILENAME"
    echo "Backup done at $DATE"
else
    rm -f "$BACKUP_DIR/$FILENAME.tmp"
    echo "Backup FAILED at $DATE" >&2
    exit 1
fi

# Deleting old backups (older than 30 days)
find $BACKUP_DIR -type f -name "*.dump" -mtime +30 -exec rm {} \;
