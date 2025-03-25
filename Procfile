web: python manage.py migrate && gunicorn label_x.wsgi:application
worker: celery -A label_x worker --loglevel=info