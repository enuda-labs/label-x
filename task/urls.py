from django.urls import path
from .apis import TaskCreateView, TaskStatusView, UserTaskListView, AssignedTaskListView, TaskReviewView

app_name = 'task'
urlpatterns = [
    path('', TaskCreateView.as_view(), name='task_create'),
    path('status/<str:identifier>/', TaskStatusView.as_view(), name='task_status'),
    path('my-tasks/', UserTaskListView.as_view(), name='user_tasks'),
    path('assigned-task', AssignedTaskListView.as_view(), name="assigned_task"),
    path('submit-review', TaskReviewView.as_view(), name="submit-review" ),
]
