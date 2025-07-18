from celery import Task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import models
from django.utils import timezone
from datetime import timedelta
from task.serializers import FullTaskSerializer
from account.models import CustomUser


def serialize_task(task):
    return FullTaskSerializer(task).data


def dispatch_task_message(receiver_id, payload, action="notification"):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_tasks_{receiver_id}",
        {"type": "task.message", "text": {"action": action, **payload}},
    )
    print("dispatched ws message")


def dispatch_review_response_message(receiver_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"reviewer_group_{receiver_id}",
        {"type": "response.message", "text": {"action": "review_response", **payload}},
    )
    print("dispatched ws message")    


def push_realtime_update(task: Task, action="notification"):
    serialized = serialize_task(task)
    if task.user:
        dispatch_task_message(task.user.id, serialized, action=action)


def assign_reviewer(task):
    """
    Assigns a reviewer to a task based on availability and workload.
    Returns True if a reviewer was assigned, False otherwise.
    """
    # Get all online reviewers who have been active in the last 5 minutes
    # Annotate with pending review count for efficient sorting
    active_reviewers = (
        CustomUser.objects.filter(
            is_reviewer=True,
            is_online=True,
            last_activity__gte=timezone.now() - timedelta(minutes=20),
        )
        .annotate(
            pending_count=models.Count(
                "assigned_tasks",
                filter=models.Q(assigned_tasks__status="REVIEW_NEEDED"),
            )
        )
        .order_by("pending_count")
    )

    if not active_reviewers.exists():
        return False

    # Get the reviewer with the least pending reviews
    reviewer = active_reviewers.first()

    # Assign the task to the reviewer
    task.assigned_to = reviewer
    task.processing_status = "REVIEW_NEEDED"
    task.save()

    # Notify the reviewer about the new task
    dispatch_task_message(reviewer.id, serialize_task(task), action='task_created')

    return True

def calculate_required_data_points(task_type, text_data=None, image_data=None, video_data=None):
    
    if task_type == 'TEXT' and text_data:
        text_length = len(text_data)
        if text_length <= 100:
            return 4
        elif text_length >100 and text_length <= 500:
            return 10
        else:
            return round(0.035 * text_length)
            
    # TODO: handle cases for other file types
    return 20