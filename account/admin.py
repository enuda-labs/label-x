from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Register your models here.
from .models import User, OTPVerification, Project, UserAPIKey, UserBankAccount, MonthlyReviewerEarnings, UserStripeConnectAccount


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin configuration for User"""
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    readonly_fields = ('date_joined', 'last_login', 'last_activity')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_reviewer', 'is_email_verified', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'last_activity')}),
        ('Project', {'fields': ('project', 'domains')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )


admin.site.register(Project)
admin.site.register(UserAPIKey)
admin.site.register(OTPVerification)
admin.site.register(UserBankAccount)
admin.site.register(MonthlyReviewerEarnings)
admin.site.register(UserStripeConnectAccount)