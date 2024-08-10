#!/bin/bash

# Settings
BACKUP_DIR=/var/backups/postgres
DATE=$(date +\%Y-\%m-\%d_\%H-\%M-\%S)
FILENAME=backup_$DATE.dump

# Backup database (on localhost)
pg_dump -U $POSTGRES_USER -h localhost -F c $POSTGRES_DB > $BACKUP_DIR/$FILENAME &&
echo Backup done at $DATE

# Deleting old backups (older than 7 days)
find $BACKUP_DIR -type f -name "*.dump" -mtime +7 -exec rm {} \;
