web: python manage.py migrate && python manage.py seed_plans && python manage.py seed_system_settings && daphne label_x.asgi:application --port 8080 --bind 0.0.0.0 -v2
worker: celery -A label_x worker --loglevel=info
beat: celery -A label_x beat -l info