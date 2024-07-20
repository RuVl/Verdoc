FROM python:3.12
LABEL authors="RuVl_13"

# Set enviroment variables
ENV TZ Europe/Moscow
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Prepare project directory
CMD mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

# Copy and install requirements
COPY ./requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project to directory
COPY . ./

# Run app
ENTRYPOINT gunicorn -c gunicorn.py backend.wsgi:application
