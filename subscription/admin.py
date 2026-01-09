from django.contrib import admin

from subscription.models import SubscriptionPlan, UserDataPoints, UserSubscription, Wallet, WalletTransaction

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'monthly_fee', 'included_data_points', 'included_requests', 'cost_per_extra_request']
    list_filter = ['name']
    search_fields = ['name']

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'user_email']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['balance']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'plan', 'is_active', 'requests_used', 'subscribed_at', 'expires_at', 'renews_at']
    list_filter = ['plan', 'subscribed_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'plan__name']
    readonly_fields = ['subscribed_at']

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'wallet', 'amount', 'status', 'reference', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['wallet__user__username', 'reference']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(UserDataPoints)
class UserDataPointsAdmin(admin.ModelAdmin):
    list_display = ['user', 'data_points_balance', 'used_data_points', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at', 'updated_at']