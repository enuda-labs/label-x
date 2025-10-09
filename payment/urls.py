from django.urls import path
from . import apis

app_name = 'payment'
urlpatterns = [
    path('paystack/banks/', apis.GetPaystackBankCodesView.as_view(), name='get-paystack-banks'),
    path('paystack/withdrawal/initiate/', apis.InitiateLabelerWithdrawalView.as_view(), name='initiate-labeler-withdrawal'),
    path('paystack/webhook/', apis.PaystackWebhookListener.as_view(), name='paystack-webhook'),
     # Earning-related endpoints
    path('earnings/current-month/', apis.LabellerEarningsView.as_view(), name='labeller-current-earnings'),
    path('earnings/history/', apis.LabellerEarningsHistoryView.as_view(), name='labeller-earnings-history'),
    path('user/transactions/', apis.FetchUserTransactionHistoryView.as_view(), name='fetch-user-transaction-history'),
    path('webhook/stripe/', apis.StripeWebhookListener.as_view(), name='stripe-webhook-listener'),

]