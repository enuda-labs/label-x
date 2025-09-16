from django.db import models
from account.models import CustomUser
from payment.choices import TransactionStatusChoices
# Create your models here.


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    usd_amount = models.DecimalField(max_digits=10, decimal_places=2)
    ngn_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="The amount in NGN")
    status = models.CharField(max_length=50, default=TransactionStatusChoices.PENDING, choices=TransactionStatusChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reference = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    bank_code = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    
    def __str__(self):
        return f"Withdrawal request of ${self.usd_amount} by {self.user.username} - {self.status}"
