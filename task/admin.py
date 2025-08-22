from django.contrib import admin
from .models import Task, TaskCluster, TaskLabel, UserReviewChatHistory

@admin.register(TaskCluster)
class TaskClusterAdmin(admin.ModelAdmin):
    list_display = ['id', 'input_type', 'task_type', 'annotation_method', 'project', 'deadline', 'labeller_per_item_count']
    list_filter = ['input_type', 'task_type', 'annotation_method', 'project']
    search_fields = ['project__name', 'labeller_instructions']
    filter_horizontal = ['assigned_reviewers']
    readonly_fields = ['id']

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['serial_no', 'task_type', 'processing_status', 'review_status', 'user', 'group', 'created_at']
    list_filter = ['task_type', 'processing_status', 'review_status', 'created_at']
    search_fields = ['serial_no', 'user__username', 'group__name']
    readonly_fields = ['serial_no', 'created_at', 'updated_at']

@admin.register(UserReviewChatHistory)
class UserReviewChatHistoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'reviewer', 'human_classification', 'human_confidence_score', 'created_at']
    list_filter = ['human_classification', 'created_at']
    search_fields = ['task__serial_no', 'reviewer__username']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(TaskLabel)
