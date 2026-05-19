#!/bin/bash

# Settings
BACKUP_DIR=/var/backups/postgres
DATE=$(date +\%Y-\%m-\%d_\%H-\%M-\%S)
FILENAME=backup_$DATE.dump

# Password for postgres utilities 
export PGPASSWORD="$POSTGRES_PASSWORD"

# Make dirs if not exist
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U "$POSTGRES_USER" -h "$DOCKER_POSTGRES_HOST" -p "$DOCKER_POSTGRES_PORT" -F c "$POSTGRES_DB" > "$BACKUP_DIR/$FILENAME" &&
echo "Backup done at $DATE"

# Deleting old backups (older than 30 days)
find $BACKUP_DIR -type f -name "*.dump" -mtime +30 -exec rm {} \;
