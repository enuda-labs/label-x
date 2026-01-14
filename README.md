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
RESEND_API_KEY=re_example_api_key
RESEND_FROM_EMAIL=example@email.com
```

**Note:** 
- Running the project locally (with `DEBUG=true`) will utilize the default SQLite database from Django. `DATABASE_URL` is only used in production.
- The `.env` file values for `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are for local development. When running in Docker, these are automatically overridden by docker-compose to use the Redis service name.

---

### 3. Start the Application

#### Option A: Development Setup (Recommended)

For development with hot-reload and separate services:

```bash
docker compose -f docker-compose.dev.yml up --build
```

This will start:
- **Web server** on port `8003` (Django development server with auto-reload)
- **Celery worker** for background task processing
- **Celery beat** for scheduled tasks
- **Redis** on port `6383` (host) → `6379` (container)

#### Option B: Production-like Setup

For a production-like setup using the main docker-compose file:

```bash
docker compose up --build
```

*or, if you have an older version of Docker Compose:*
```bash
docker-compose up --build
```

- This will automatically install all requirements, run migrations, seed plans and system settings, and configure Redis and Celery.

---

### 4. Create a Superuser (Admin)

For development setup:
```bash
docker exec -it label-x-web-1 bash
python manage.py createsuperuser
```

For production-like setup:
```bash
docker exec -it label_x bash
python manage.py createsuperuser
```

---

### 5. Access the UI

- **API Documentation (Swagger)**: [http://localhost:8003/api/docs](http://localhost:8003/api/docs)
- **Admin Panel**: [http://localhost:8003/admin](http://localhost:8003/admin) - Login with the credentials you created.

---

## 🐳 Docker Services

When using `docker-compose.dev.yml`, the following services are available:

- **web**: Django development server (port 8003)
- **celery**: Celery worker for processing background tasks
- **celery-beat**: Celery beat scheduler for periodic tasks
- **redis**: Redis server for caching and Celery message broker (port 6383 on host)

---

## 🔧 Useful Docker Commands

### View Logs
```bash
# All services
docker compose -f docker-compose.dev.yml logs -f

# Specific service
docker compose -f docker-compose.dev.yml logs -f web
docker compose -f docker-compose.dev.yml logs -f celery
docker compose -f docker-compose.dev.yml logs -f celery-beat
```

### Stop Services
```bash
docker compose -f docker-compose.dev.yml down
```

### Restart a Specific Service
```bash
docker compose -f docker-compose.dev.yml restart web
docker compose -f docker-compose.dev.yml restart celery
docker compose -f docker-compose.dev.yml restart celery-beat
```

### Execute Commands in Container
```bash
# Access web container shell
docker exec -it label-x-web-1 bash

# Run Django management commands
docker exec -it label-x-web-1 python manage.py <command>
```

---

## 🔍 Troubleshooting

### Redis Connection Issues

If you see errors about Redis connection:
- Ensure Redis container is running: `docker ps | grep redis`
- Check Redis logs: `docker compose -f docker-compose.dev.yml logs redis`
- The docker-compose.dev.yml automatically sets `CELERY_BROKER_URL=redis://redis:6379/0` which uses the Redis service name for container-to-container communication.

### Port Already in Use

If port 8003 is already in use, you can change it in `docker-compose.dev.yml`:
```yaml
ports:
  - "8004:8003"  # Change 8004 to any available port
```

### Database Issues

- The project uses SQLite by default in development (when `DEBUG=true`)
- Migrations run automatically on container startup
- To reset the database, delete `db.sqlite3` and restart containers

---

## 👥 Team Member Management

Projects support team collaboration with role-based access control.

### Access Levels

- **Owner**: Full access (create tasks, view tasks, manage members, manage project settings)
- **Admin**: Can create tasks, view tasks, and manage team members
- **Member**: Can create and view tasks
- **Viewer**: Read-only access (view tasks only)

### Features

- Add existing users to projects
- Invite new users via email (creates account if needed)
- Update member roles
- Remove team members
- Project creator is automatically added as Owner

### API Endpoints

- `GET /api/v1/account/projects/<project_id>/members/` - List project members
- `POST /api/v1/account/projects/<project_id>/members/add/` - Add existing user
- `POST /api/v1/account/projects/<project_id>/invitations/send/` - Send invitation
- `PATCH /api/v1/account/projects/<project_id>/members/<user_id>/role/` - Update role
- `DELETE /api/v1/account/projects/<project_id>/members/<user_id>/` - Remove member
- `POST /api/v1/account/projects/invitations/<token>/accept/` - Accept invitation




