web: python manage.py migrate && python manage.py seed_plans && python manage.py seed_system_settings && daphne label_x.asgi:application --port 8003 --bind 0.0.0.0 -v2
worker: celery -A label_x worker --loglevel=info --concurrency=1
beat: celery -A label_x beat -l info