from celery import Task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from task.serializers import TaskSerializer, TaskStatusSerializer


def serialize_task(task):
    return TaskStatusSerializer(task).data


def dispatch_task_message(receiver_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_tasks_{receiver_id}", {"type": "task.message", "text": payload}
    )
    print("dispatched ws message")


def push_realtime_update(task: Task):
    serialized = serialize_task(task)
    print(task.user.id)
    dispatch_task_message(task.user.id, serialized)
