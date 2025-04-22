from django.contrib import admin

from task.models import Task, UserReviewChatHistory

# Register your models here.
admin.site.register(Task)
admin.site.register(UserReviewChatHistory)
