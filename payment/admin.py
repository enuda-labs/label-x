from django.contrib import admin

from payment.models import MonthlyPayment, Transaction, WithdrawalRequest

admin.site.register(WithdrawalRequest)
admin.site.register(Transaction)
admin.site.register(MonthlyPayment)