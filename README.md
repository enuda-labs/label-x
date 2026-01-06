# 🚀 Running LabelX Backend Locally

This guide explains how to set up and run the LabelX backend project on your local machine using Docker for consistent and isolated development.

---

## 📋 Prerequisites

- **Docker** (latest version: [Get Docker](https://www.docker.com/products/docker-desktop/))
- **Docker Compose** (if not included with Docker)
- **Git**

---

## 🛠️ Installation & Setup (with Docker)

### 1. Clone the Repository

```bash
git clone https://github.com/enuda-labs/label-x
cd label-x
```

---

### 2. Configure Environment Variables

Create a `.env` file in the project root directory. Example content:



```
SECRET_KEY_VALUE=example_secret_key
DEBUG_VALUE=true
ALLOWED_HOSTS_VALUE=localhost,127.0.0.1
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
DATABASE_URL=postgres://user:password@localhost:5432/dbname
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
CO_API_KEY=cohere_exampleapikey
STRIPE_SECRET_KEY=sk_test_example
STRIPE_PUBLISHABLE_KEY=pk_test_example
STRIPE_WEBHOOK_SECRET=whsec_example
STRIPE_CONNECT_WEBHOOK_SECRET=whsec_connect_example
CLOUDINARY_API_SECRET=cloudinary_example_api_secret
CLOUDINARY_API_KEY=cloudinary_example_api_key
CLOUDINARY_CLOUD_NAME=cloudinary_example_cloud
STARTER_PLAN_ID=stripe_starter_plan_example_id
TEAMS_PLAN_ID=stripe_teams_plan_example_id
ENTERPRISE_PLAN_ID=stripe_enterprise_plan_example_id
REDIS_CACHE_BACKEND=redis://localhost:6379/1
PAYSTACK_SECRET_KEY=paystack_example_secret
PAYSTACK_PUBLIC_KEY=paystack_example_public
EXCHANGE_RATE_API_KEY=exchange_rate_example_key
BREVO_API_KEY=brevo_example_api_key
BREVO_FROM_EMAIL=example@email.com
```

**Note:** 
- Running the project locally i.e with DEBUG=true will utilize the default sqlite database from django, DATABASE_URL is only used in production
---

### 3. Start the Application

Build and start the containers (backend + database):

```bash
docker compose up --build
```
*or, if you have an older version of Docker Compose:*
```bash
docker-compose up --build
```

- This will automatically install all requirements, Make migrations and configure redis, celery



---

### 4. Create a Superuser (Admin)

```bash
docker exec -it label_x bash

python manage.py createsuperuser
```



### 5. Access the UI

Visit [http://localhost:8080/api/docs](http://localhost:8080/api/docs) for the swagger ui documentation

Visit [http://localhost:8080/admin](http://localhost:8080/admin) and login with the credentials you created.



# Optional Configuration for Development

If you want the Docker container to automatically reload during development, follow these steps:

### 1. Create a Procfile.dev
In the same directory as your main Procfile, create a new file called `Procfile.dev`. This file should use Django's `runserver` command instead of `daphne`:

```
web: python manage.py migrate && python manage.py seed_plans && python manage.py seed_system_settings && python manage.py runserver 0.0.0.0:8080
worker: celery -A label_x worker --loglevel=info
beat: celery -A label_x beat -l info

```

### 2. Create a docker-compose.override.yml
In the same directory as your `docker-compose.yml` file, add a `docker-compose.override.yml`. This file will instruct Docker to use the `Procfile.dev` you just created.

```yml
version: "3.8"

services:
  app:
    build: .
    volumes:
      - .:/app
    env_file:
      - ./.env
    ports:
      - "8080:8080"
    container_name: "label_x"
    depends_on:
      - redis
    command: ['honcho', 'start', '-f', 'Procfile.dev']

  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

### 3. Build and Start the Container
With the override file in place, you can now build and run the containers using:

```bash
docker compose up --build
```




