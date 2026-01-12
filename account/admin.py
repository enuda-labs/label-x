from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Register your models here.
from .models import User, OTPVerification, Project, UserAPIKey, UserBankAccount, MonthlyReviewerEarnings, UserStripeConnectAccount


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin configuration for User"""
    list_display = ('username', 'email', 'user_type', 'is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'date_joined')
    list_filter = ('is_reviewer', 'is_staff', 'is_superuser', 'is_active', 'is_email_verified', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    readonly_fields = ('date_joined', 'last_login', 'last_activity')
    
    def user_type(self, obj):
        if obj.is_superuser:
            return "Superuser"
        elif obj.is_staff:
            return "Admin"
        elif obj.is_reviewer:
            return "Labeler"
        else:
            return "Client"
    user_type.short_description = 'User Type'
    
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


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'created_by', 'created_at', 'cluster_count']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    
    def cluster_count(self, obj):
        return obj.clusters.count()
    cluster_count.short_description = 'Clusters'

@admin.register(UserAPIKey)
class UserAPIKeyAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'key_type', 'created', 'revoked']
    list_filter = ['key_type', 'created', 'revoked']
    search_fields = ['name', 'user__username', 'user__email']
    readonly_fields = ['created', 'revoked']

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_verified', 'created_at', 'updated_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'secret_key']

@admin.register(UserBankAccount)
class UserBankAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'bank_name', 'account_number', 'account_name', 'platform', 'is_primary', 'created_at']
    list_filter = ['platform', 'is_primary', 'created_at']
    search_fields = ['user__username', 'account_number', 'bank_name', 'account_name']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(MonthlyReviewerEarnings)
class MonthlyReviewerEarningsAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'year', 'month', 'total_earnings_usd', 'usd_balance', 'release_status', 'created_at']
    list_filter = ['release_status', 'year', 'month', 'created_at']
    search_fields = ['reviewer__username', 'reviewer__email']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-year', '-month', '-created_at']

@admin.register(UserStripeConnectAccount)
class UserStripeConnectAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'account_id', 'status', 'payouts_enabled', 'created_at', 'updated_at']
    list_filter = ['status', 'payouts_enabled', 'created_at']
    search_fields = ['user__username', 'account_id']
    readonly_fields = ['created_at', 'updated_at']