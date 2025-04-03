# web: python manage.py migrate && python manage.py runserver 0.0.0.0:8080
web: python manage.py migrate && gunicorn -b 0.0.0.0:8080 label_x.wsgi:application
worker: celery -A label_x worker --loglevel=info