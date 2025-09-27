from django.db import models
from account.models import CustomUser
from payment.choices import TransactionStatusChoices, TransactionTypeChoices, WithdrawalRequestInitiatedByChoices
import uuid
# Create your models here.


class Transaction(models.Model):
    #any transaction that involves money should be stored here
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    usd_amount = models.DecimalField(max_digits=10, decimal_places=2)
    ngn_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="The amount in NGN at the time of the transaction")#this is optional, i added it solely for paystack
    status = models.CharField(max_length=50, default=TransactionStatusChoices.PENDING, choices=TransactionStatusChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_type = models.CharField(max_length=50, default=TransactionTypeChoices.WITHDRAWAL, choices=TransactionTypeChoices.choices)
    description = models.TextField(null=True, blank=True, help_text="The description of the transaction")
    
    def mark_failed(self):
        self.status = TransactionStatusChoices.FAILED
        self.save(update_fields=['status'])
    
    def mark_success(self):
        self.status = TransactionStatusChoices.SUCCESS
        self.save(update_fields=['status'])
    
    def __str__(self):
        return f"{self.transaction_type} transaction of ${self.usd_amount} by {self.user.username} - {self.status}"



class WithdrawalRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reference = models.CharField(max_length=255)
    account_number = models.CharField(max_length=255)
    bank_code = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    is_user_balance_deducted = models.BooleanField(default=False, help_text="Whether the user's balance has been deducted for this withdrawal request")
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True, help_text="The transaction that this withdrawal request is associated with")
    initiated_by = models.CharField(max_length=50, choices=WithdrawalRequestInitiatedByChoices.choices, default=WithdrawalRequestInitiatedByChoices.USER, help_text="Whether the withdrawal request was initiated by the user or the system")
    
    def __str__(self):
        return f"Withdrawal request to {self.bank_name} account number {self.account_number}"
        # return f"Withdrawal request of ${self.transaction.usd_amount} by {self.transaction.username} - {self.transaction.status}"
    

