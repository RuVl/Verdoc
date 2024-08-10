FROM postgres:16.2

# Install cron
RUN apt-get update && apt-get install -y cron

# Create the cronjob's log file
RUN touch /var/log/cron.log

# Copy a backup script and setting execution rights
COPY backup.sh /usr/local/bin/backup_postgres.sh
RUN chmod +x /usr/local/bin/backup_postgres.sh

# Copy the cronjob and apply it
COPY cronjob /etc/cron.d/backup-cron
RUN crontab /etc/cron.d/backup-cron

# Running cron in background and PostgreSQL in foreiground
CMD service cron start && docker-entrypoint.sh postgres
