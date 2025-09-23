from django.contrib import admin

from payment.models import Transaction, WithdrawalRequest

admin.site.register(WithdrawalRequest)
admin.site.register(Transaction)