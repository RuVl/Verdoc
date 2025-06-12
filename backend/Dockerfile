FROM python:3.12
LABEL authors="RuVl_13"

# Set enviroment variables
ENV TZ=Europe/Moscow
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install cron
RUN apt-get update && apt-get install -y cron

# Create the cronjob's log file
RUN touch /var/log/cron.log

# Prepare project directory
RUN mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

# Copy and install requirements
COPY ./requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project to directory
COPY . ./

# Copy the cronjob, apply it
COPY cronjob /etc/cron.d/expire-orders-cron
RUN crontab /etc/cron.d/expire-orders-cron

# Run gunicorn
RUN chmod +x ./startup.sh
ENTRYPOINT ["./startup.sh", "gunicorn", "-c", "gunicorn.py", "backend.wsgi:application"]