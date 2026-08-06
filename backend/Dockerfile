FROM docker.io/library/python:3.13-slim
LABEL authors="RuVl_13"

# uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

# Set enviroment variables
ENV TZ=Europe/Moscow
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install cron, and gettext for `compilemessages` (translated e-mail copy)
RUN apt-get update && apt-get -y install cron gettext && apt-get -y autoremove

# Create the cronjob's log file
RUN touch /var/log/cron.log

# Prepare project directory
WORKDIR /app

# Install dependencies from the lockfile (cached layer, no project code yet)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy project to directory
COPY . .

# Copy the cronjob, apply it
COPY cronjob /etc/cron.d/expire-orders-cron
RUN crontab /etc/cron.d/expire-orders-cron

# Run gunicorn
RUN chmod +x ./startup.sh
ENTRYPOINT ["./startup.sh", "uv", "run", "gunicorn", "-c", "gunicorn.py", "backend.wsgi:application"]
