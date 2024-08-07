# Verdoc
Verif-docs is a document purchase platform built with Vue.js for the frontend and Django REST Framework (DRF) for the backend, 
with nginx handling proxying and serving in Docker containers.

## Getting Started

### Prerequisites
* Docker and Docker Compose installed on your machine.
* SSL certificates for HTTPS, placed in `frontend/nginx/ssl` (with `.key` and `.crt` extensions).
* API tokens for _Plisio_, _OpenExchangeRates_, and _Google Mail_.

### Setup
1. **Clone the Repository**
    ```bash
    git clone https://github.com/your-username/verif-docs.git
    cd verif-docs
    ```
2. **Environment Configuration** \
Set up the environment variables by copying the `.env.dist` files to `.env` files in the respective directories (`frontend`, `backend`, and 
   `postgres`) and changing them.
3. **Build and Run Docker Containers**
    ```bash
    docker-compose up -d --build
    ```
4. **Initial Database Setup** \
After starting the containers, access the backend container and run the following commands:
    ```bash
    docker exec -it backend_container_name bash
    python manage.py makemigrations
    python manage.py migrate
    ```
5. **Update Site Configuration**
Update the `django_site` table in the database to reflect your domain:
    ```postgresql
    UPDATE django_site SET domain='your-domain', name='human-readable name' WHERE id=1;
    ```

### Features
1. **Product Reservation** \
When an order is created, the products are reserved.
If the order is not completed within one hour, the reservation expires, and the products are made available again.

2. **Payment and Download Links** \
Upon order creation, users are redirected to the payment site. After successful payment, download links are sent to the provided email.

3. **Currency Exchange** \
To update the currency exchange rates, press the corresponding button in the Django admin panel.

## Technology Stack

### Frontend
* `Vue.js` - Core framework
* `Pinia` - State management
* `Axios` - HTTP client
* `Lodash` - Utility functions
* `Vue Router` - Routing
* `Vue I18n` - Internationalization
* `Vue Country Flag` - Country flags

### Backend
* `Django` - Core framework
* `Django REST Framework (DRF)` - API framework
* `Django Model Translation` - Model translations
* `Django Money` - Money and currency support
* `Gunicorn` - WSGI HTTP server
* `Psycopg` - PostgreSQL adapter

### Additional Configurations
* SSL Certificates: Required for HTTPS, placed in `frontend/nginx/ssl`.
* Environment Variables: Ensure `PORT` is set correctly if the backend container does not use port `8000`.

### Translation and State Management
* `i18n`: Used for translations on both frontend and backend.
* `Pinia`: Manages state, especially for the cart and user preferences.
* `Currency Switching`: Allows users to switch currencies seamlessly.

## Contributing
Feel free to fork the repository and submit pull requests. For major changes, please open an issue first to discuss what you would like to change.

### License
Distributed under the **GPLv3** License. See LICENSE for more information.