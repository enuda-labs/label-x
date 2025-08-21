from django.contrib import admin

from task.models import MultiChoiceOption, Task, TaskCluster, UserReviewChatHistory

# Register your models here.
admin.site.register(Task)
admin.site.register(UserReviewChatHistory)
admin.site.register(TaskCluster)
admin.site.register(MultiChoiceOption)
