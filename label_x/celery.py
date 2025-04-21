from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'label_x.settings')
os.environ['FORKED_BY_MULTIPROCESSING'] = '1'

celery_app = Celery('label_x')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
celery_app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
celery_app.autodiscover_tasks()

# Configure Celery Beat schedule
celery_app.conf.beat_schedule = {
    'update-user-online-status': {
        'task': 'account.periodic_tasks.update_user_online_status',
        'schedule': crontab(minute='*/1'),  # Run every minute
    },
}

@celery_app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

# Optional Redis configuration - will attempt to connect but fail gracefully
celery_app.conf.broker_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery_app.conf.result_backend = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Configure better error handling
celery_app.conf.broker_connection_retry = True
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_connection_max_retries = 3
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True


# Configure task queues with priorities
celery_app.conf.task_routes = {
    'task.tasks.process_task': {'queue': 'default'},
    'task.tasks.process_with_ai_model': {'queue': 'ai_queue'},
    'task.tasks.route_task_to_processing': {'queue': 'default'},
    'task.tasks.queue_task_for_processing': {'queue': 'default'},
    'task.tasks.provide_feedback_to_ai_model': {'queue': 'default'},
    'task.tasks.submit_human_review_history': {'queue': 'default'},
}

CELERY_TASK_QUEUES = {
    'default': {'routing_key': 'default', 'priority': 5},
    'ai_queue': {'routing_key': 'ai', 'priority': 5},
    'urgent_queue': {'routing_key': 'urgent', 'priority': 9},
    'normal_queue': {'routing_key': 'normal', 'priority': 5},
    'low_queue': {'routing_key': 'low', 'priority': 1},
}
celery_app.conf.task_queues = CELERY_TASK_QUEUES

# Configure queue priorities
celery_app.conf.broker_transport_options = {
    'priority_steps': list(range(10)),
    'queue_order_strategy': 'priority',
}
