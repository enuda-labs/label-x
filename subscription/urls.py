from django.urls import path
from . import apis

urlpatterns = [
    path("plans", apis.ListSubscriptionPlansView.as_view(), name="subscription_plans"),
    path("subscribe/", apis.SubscribeToPlanView.as_view(), name="subscribe"),
    path("my_plan/", apis.CurrentSubscriptionView.as_view(), name="my_plan"),
    path('webhook/stripe/', apis.StripeWebhookListener.as_view(), name='stripe-webhook-listener'),
    path('initialize/', apis.InitializeStripeSubscription.as_view(), name='initialize-stripe-subscription'),
    path('payment/history/', apis.GetUserPaymentHistoryView.as_view(), name="get-user-payment-history")
]
