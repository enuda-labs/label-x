# web: python manage.py migrate && python manage.py seed_plans && python manage.py runserver 0.0.0.0:8080
web: python manage.py migrate && python manage.py seed_plans && python manage.py seed_system_settings && daphne label_x.asgi:application --port 8080 --bind 0.0.0.0 -v2
# web: python manage.py migrate && gunicorn -b 0.0.0.0:8080 label_x.wsgi:application
worker: celery -A label_x worker --loglevel=info --concurrency=1
