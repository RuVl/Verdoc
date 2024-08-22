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
CMD mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

# Copy and install requirements
COPY ./requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project to directory
COPY . ./

# Collect django's static files
CMD python3 manage.py collectstatic --no-input

# Copy the cronjob, apply it, and run cron
COPY cronjob /etc/cron.d/expire-orders-cron
RUN crontab /etc/cron.d/expire-orders-cron
RUN nohup service cron start &

# Run gunicron
ENTRYPOINT gunicorn -c gunicorn.py --access-logfile - --error-logfile - backend.wsgi:application
