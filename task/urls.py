from django.urls import path
from . import apis

app_name = 'task'
urlpatterns = [
    path('', apis.TaskCreateView.as_view(), name='task_create'),
    path('review-needed/', apis.TasksNeedingReviewView.as_view(), name='tasks_review_needed'),
    path('assign-to-me/', apis.AssignTaskToSelfView.as_view(), name='assign_task_to_self'),
    path('my-pending-reviews/', apis.MyPendingReviewTasks.as_view(), name='my_pending_reviews'),
    
    path('status/<str:identifier>/', apis.TaskStatusView.as_view(), name='task_status'),
    path('my-tasks/', apis.UserTaskListView.as_view(), name='user_tasks'),
    path('assigned-task', apis.AssignedTaskListView.as_view(), name="assigned_task"),
    path('submit-review', apis.TaskReviewView.as_view(), name="submit-review" ),
    path('review/complete/', apis.CompleteTaskReviewView.as_view(), name='complete-task-review'),
    path('completion-stats/', apis.TaskCompletionStatsView.as_view(), name='task_completion_stats')
    # path('list/', apis.TaskListView.as_view(), name='list-tasks')
]
