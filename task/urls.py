from django.urls import path
from .apis import TaskCreateView

app_name = 'task'
urlpatterns = [
    path('', TaskCreateView.as_view(), name='task_create')
]
