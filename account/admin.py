from django.contrib import admin

# Register your models here.
from .models import CustomUser, LabelerEarnings, OTPVerification, Project, UserAPIKey, UserBankAccount, MonthlyReviewerEarnings

admin.site.register(CustomUser)
admin.site.register(Project)
admin.site.register(UserAPIKey)
admin.site.register(OTPVerification)
admin.site.register(LabelerEarnings)
admin.site.register(UserBankAccount)


admin.site.register(MonthlyReviewerEarnings)
