from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta
from .models import CustomUser

logger = get_task_logger(__name__)

@shared_task
def update_user_online_status():
    """
    Periodic task to update user online status.
    Users are considered offline if they haven't been active in the last 5 minutes.
    """
    logger.info("Starting user online status update")
    
    # Get current time
    now = timezone.now()
    offline_threshold = now - timedelta(minutes=5)
    
    # Update users who haven't been active in the last 5 minutes
    offline_users = CustomUser.objects.filter(
        is_online=True,
        last_activity__lt=offline_threshold
    )
    
    # Update users who have been active in the last 5 minutes
    online_users = CustomUser.objects.filter(
        last_activity__gte=offline_threshold
    )
    
    # Update statuses
    offline_users.update(is_online=False)
    online_users.update(is_online=True)
    
    logger.info(f"Updated {offline_users.count()} users to offline")
    logger.info(f"Updated {online_users.count()} users to online")
    
    return {
        'offline_users': offline_users.count(),
        'online_users': online_users.count()
    } 