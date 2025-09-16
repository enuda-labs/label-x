from celery import Task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import models
from django.utils import timezone
from datetime import timedelta
from task.choices import TaskTypeChoices
from account.models import CustomUser
import math
from task.models import TaskCluster

def serialize_task(task):
    from task.serializers import FullTaskSerializer

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


def calculate_labelling_required_data_points(cluster_data:dict)->int:
    datapoint = 10 #you automatically spend 10 data points for creating a cluster
        
    response_type_datapoint_mapping = {
        "video": 10,
        "audio": 10,
        "image": 5,
        "text": 1,
        "multiple_choice": 1,
        "voice": 10,
    }
    
    task_type_datapoint_mapping = {
        TaskTypeChoices.TEXT: 5,
        TaskTypeChoices.IMAGE: 10,
        TaskTypeChoices.VIDEO: 20,
        TaskTypeChoices.AUDIO: 15,
        TaskTypeChoices.CSV: 8,
    }
    
    datapoint += response_type_datapoint_mapping.get(cluster_data.get('input_type'), 0)
    datapoint += task_type_datapoint_mapping.get(cluster_data.get('task_type'), 0)
    dp_cost_per_labeller = 10
    
    #two extra datapoints for every 5 labellers
    # datapoint += math.ceil((cluster.labeller_per_item_count / 5) * 2)
    datapoint += cluster_data.get('labeller_per_item_count') * dp_cost_per_labeller

    return datapoint

def calculate_required_data_points(task_type, text_data=None, file_size_bytes=None)->int:
    """
    Calculate the number of data points required to process a task based on its type and content.
    
    This function determines the cost (in data points) for processing different types of tasks.
    Data points are consumed based on the complexity and resource requirements of each task type.
    
    Args:
        task_type (str): The type of task (TEXT, AUDIO, IMAGE, VIDEO, etc.)
        text_data (str, optional): The text content for text-based tasks
        file_size_bytes (int, optional): File size in bytes for file-based tasks
    
    Returns:
        int: Number of data points required to process the task
        
    """
    
    if task_type == 'TEXT' and text_data:
        text_length = len(text_data)
        if text_length <= 100:
            return 4
        elif text_length >100 and text_length <= 500:
            return 10
        else:
            return round(0.035 * text_length)
    
    if file_size_bytes and task_type in [TaskTypeChoices.AUDIO, TaskTypeChoices.IMAGE, TaskTypeChoices.VIDEO]:
        # Convert bytes to megabytes for easier calculation
        size_in_mb = file_size_bytes / (1024 * 1024)
        
        if task_type == TaskTypeChoices.AUDIO:
            # Audio: 10 points per MB, minimum 10 points
            return max(10, round(10 * size_in_mb))
            
        elif task_type == TaskTypeChoices.IMAGE:
            # Image: 5 points per MB, minimum 10 points
            return max(10, round(5 * size_in_mb))
            
        elif task_type == TaskTypeChoices.VIDEO:
            # Video: 15 points per MB, minimum 10 points
            return max(10, round(15 * size_in_mb))        
    return 20