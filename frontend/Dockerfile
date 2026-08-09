# Use node.js for building the frontend
FROM docker.io/library/node:22.12-alpine3.21 AS build-stage
LABEL authors="RuVl_13"

# Set enviroment variables
ENV TZ=Europe/Moscow

# Prepare project directory
WORKDIR /app

# Install dependencies
COPY package.json ./
RUN npm install --verbose

# Copy source and build frontend
COPY . .
RUN npm run build


# Use nginx for serving the static files
FROM docker.io/library/nginx:1.26.0
LABEL authors="RuVl_13"

# Set enviroment variables
ENV TZ=Europe/Moscow
ENV NGINX_ENVSUBST_TEMPLATE_SUFFIX=.template
ENV NGINX_ENVSUBST_OUTPUT_DIR=/etc/nginx/conf.d
ENV NGINX_ENVSUBST_FILTER='DOMAIN'

# Install envsubst
RUN apt-get update && \
    apt-get install -y gettext-base && \
    rm -rf /var/lib/apt/lists/*

# Copy frontend build
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy nginx template
COPY nginx/site.conf.template /etc/nginx/templates/verif-docs.conf.template
COPY nginx/mirror.conf.template /etc/nginx/templates/photo-scan.conf.template

# Rate-limit zones (http context, declared once) and the blocks both site templates include.
# Not templates themselves: they carry no ${DOMAIN}, and the zones must be declared exactly once.
COPY nginx/00-limits.conf /etc/nginx/conf.d/00-limits.conf
COPY nginx/proxy-backend.conf /etc/nginx/proxy-backend.conf
COPY nginx/site-body.conf /etc/nginx/site-body.conf

# Copy SSL certificates
COPY ./nginx/ssl/ /etc/ssl/

# Prepare logs
RUN mkdir -p /usr/www/logs && \
    touch /usr/www/logs/nginx_access.log && \
    touch /usr/www/logs/nginx_error.log

# Generate nginx config from template and run nginx
# (automatically from nginx's Dockerfile)
