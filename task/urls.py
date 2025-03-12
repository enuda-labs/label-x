from django.urls import path
from .apis import TaskCreateView

urlpatterns = [
    path('', TaskCreateView.as_view(), name='task_create')
]
