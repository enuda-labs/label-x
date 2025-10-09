from django.contrib import admin

# Register your models here.
from .models import CustomUser, OTPVerification, Project, UserAPIKey, UserBankAccount, MonthlyReviewerEarnings, UserStripeConnectAccount

admin.site.register(CustomUser)
admin.site.register(Project)
admin.site.register(UserAPIKey)
admin.site.register(OTPVerification)
admin.site.register(UserBankAccount)


admin.site.register(MonthlyReviewerEarnings)
admin.site.register(UserStripeConnectAccount)

#