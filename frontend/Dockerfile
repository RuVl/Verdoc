# Use Node.js for building the frontend
FROM node:20.14.0 AS build-stage
LABEL authors="RuVl_13"

# Set enviroment variables
ENV TZ Europe/Moscow

# Prepare project directory
CMD mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

# Copy and install dependencies
COPY ./package*.json ./
RUN npm install

# Copy project to directory
COPY . ./
RUN npm run build

# Use Nginx for serving the static files
FROM nginx:1.26.0
LABEL authors="RuVl_13"

# Copy built files to Nginx
COPY --from=build-stage /usr/src/app/dist /usr/share/nginx/html

# Copy the nginx configuration file
COPY ./nginx/verdoc.conf /etc/nginx/conf.d/

CMD mkdir -p /usr/www/logs && touch /usr/www/logs/nginx_access.log

# Expose the port 80
EXPOSE 80

# Start Nginx to serve the application (in foreground)
ENTRYPOINT nginx -g daemon off
