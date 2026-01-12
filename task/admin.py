from django.contrib import admin
from .models import ManualReviewSession, MultiChoiceOption, Task, TaskCluster, TaskLabel, UserReviewChatHistory

@admin.register(TaskCluster)
class TaskClusterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'task_type', 'annotation_method', 'project', 'status', 'completion_percentage', 'labeller_per_item_count', 'created_at']
    list_filter = ['input_type', 'task_type', 'annotation_method', 'status', 'project', 'created_at']
    search_fields = ['name', 'project__name', 'labeller_instructions', 'description']
    filter_horizontal = ['assigned_reviewers']
    readonly_fields = ['id', 'created_at', 'updated_at']

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

@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ['id', 'task', 'labeller', 'label_preview', 'created_at']
    list_filter = ['created_at', 'labeller']
    search_fields = ['task__serial_no', 'labeller__username', 'label']
    readonly_fields = ['created_at', 'updated_at']
    
    def label_preview(self, obj):
        if obj.label:
            return obj.label[:50] + '...' if len(obj.label) > 50 else obj.label
        elif obj.label_file_url:
            return f"File: {obj.label_file_url[:50]}..."
        return "—"
    label_preview.short_description = 'Label'

@admin.register(MultiChoiceOption)
class MultiChoiceOptionAdmin(admin.ModelAdmin):
    list_display = ['option_text', 'cluster', 'cluster_project']
    list_filter = ['cluster__task_type', 'cluster__project']
    search_fields = ['option_text', 'cluster__name', 'cluster__project__name']
    
    def cluster_project(self, obj):
        return obj.cluster.project.name
    cluster_project.short_description = 'Project'

@admin.register(ManualReviewSession)
class ManualReviewSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'labeller', 'cluster', 'cluster_project', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at', 'cluster__project']
    search_fields = ['labeller__username', 'cluster__name', 'cluster__project__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def cluster_project(self, obj):
        return obj.cluster.project.name
    cluster_project.short_description = 'Project'
