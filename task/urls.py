from django.urls import path
from .apis import TaskCreateView, TaskStatusView, UserTaskListView

app_name = 'task'
urlpatterns = [
    path('', TaskCreateView.as_view(), name='task_create'),
    path('status/<str:identifier>/', TaskStatusView.as_view(), name='task_status'),
    path('my-tasks/', UserTaskListView.as_view(), name='user_tasks'),
]
