web: python manage.py migrate && gunicorn -b 0.0.0.0:8080 label_x.wsgi:application --log-file -
worker: celery -A label_x worker --loglevel=info