FROM docker.io/library/postgres:16.2

# Install cron
RUN apt-get update \
  && apt-get install -y --no-install-recommends cron \
  && rm -rf /var/lib/apt/lists/*

# Copy the backup script and the entrypoint wrapper
COPY backup.sh /usr/local/bin/backup_postgres.sh
COPY entrypoint.sh /usr/local/bin/pg-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/backup_postgres.sh /usr/local/bin/pg-entrypoint.sh \
  && chmod +x /usr/local/bin/backup_postgres.sh /usr/local/bin/pg-entrypoint.sh

# Copy the cronjob and apply it
COPY cronjob /etc/cron.d/backup-cron
RUN crontab /etc/cron.d/backup-cron

# The wrapper starts cron, then execs the stock entrypoint
ENTRYPOINT ["/usr/local/bin/pg-entrypoint.sh"]
CMD ["postgres"]
