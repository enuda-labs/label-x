from django.contrib import admin

from subscription.models import SubscriptionPlan, UserDataPoints, UserSubscription, Wallet, WalletTransaction

admin.site.register(SubscriptionPlan)
admin.site.register(Wallet)
admin.site.register(UserSubscription)
admin.site.register(WalletTransaction)
admin.site.register(UserDataPoints)