import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'label_x.settings')
os.environ['FORKED_BY_MULTIPROCESSING'] = '1'

celery_app = Celery('labelx_content_moderation')
celery_app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in installed apps
celery_app.autodiscover_tasks()

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
    'moderation.tasks.process_task': {'queue': 'default'},
    'moderation.tasks.process_with_ai_model': {
        'queue': lambda task_request: {
            'urgent': 'urgent_queue',
            'normal': 'normal_queue',
            'low': 'low_queue',
        }.get(task_request.kwargs.get('priority', 'normal'))
    }
}

# Configure queue priorities
celery_app.conf.broker_transport_options = {
    'priority_steps': list(range(10)),
    'queue_order_strategy': 'priority',
}
