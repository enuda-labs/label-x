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
    path('completion-stats/', apis.TaskCompletionStatsView.as_view(), name='task_completion_stats'),
    path('cluster/', apis.TaskClusterCreateView.as_view(), name='task-cluster-create'),
    path('my-assigned-clusters/', apis.MyAssignedClustersView.as_view(), name='my_assigned_clusters'),
    
    # Annotation endpoints
    path('annotate/', apis.TaskAnnotationView.as_view(), name='task_annotation'),
    path('cluster/<int:cluster_id>/progress/', apis.ClusterAnnotationProgressView.as_view(), name='cluster_progress'),
    path('available-for-annotation/', apis.AvailableTasksForAnnotationView.as_view(), name='available_tasks'),
    
    # Label management endpoints
    path('labels/<int:task_id>/', apis.TaskLabelsView.as_view(), name='task_labels'),
    path('cluster/<int:cluster_id>/labels-summary/', apis.ClusterLabelsSummaryView.as_view(), name='cluster_labels_summary'),
    path('cluster/assign-to-self/', apis.AssignClusterToSelf.as_view(), name='assign-cluster-to-self'),
    path('cluster/user/list/', apis.CreatedClusterListView.as_view(), name='get-created-clusters'),
    path('cluster/<int:id>/', apis.GetClusterDetailView.as_view(), name='get-cluster-details'),
    path('cluster/available/', apis.GetAvailableClusters.as_view(), name='get-available-clusters'),
    path('cluster/<int:cluster_id>/tasks/user-annotated/', apis.UserClusterAnnotatedTasksView.as_view(), name='user-cluster-annotated-tasks'),
    path('cluster/user/pending/', apis.GetPendingClusters.as_view(), name='get-pending-clusters'),
    path('project/<int:project_id>/clusters/', apis.GetProjectClusters.as_view(), name='get-project-clusters'),
    path('cluster/<int:cluster_id>/reviewers/', apis.GetClusterReviewers.as_view(), name='get-cluster-reviewers'),
    path('cluster/<int:cluster_id>/assign-reviewers/', apis.AssignReviewersToCluster.as_view(), name='assign-reviewers-to-cluster'),
    path('cluster/<int:cluster_id>/remove-reviewers/', apis.RemoveReviewersFromCluster.as_view(), name='remove-reviewers-from-cluster'),

    # path('list/', apis.TaskListView.as_view(), name='list-tasks')
]
