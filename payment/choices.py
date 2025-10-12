from django.db import models


class TransactionTypeChoices(models.TextChoices):
    WITHDRAWAL = 'withdrawal', 'Withdrawal' #user withdrawing money from their account
    DEPOSIT = 'deposit', 'Deposit' #money was deposited into users account (after labelling a task perhaps)
    MONTHLY_PAYMENT = 'monthly_payment', 'Monthly Payment' #money was credited to the labeller's account for the month

class TransactionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending' #transaction has been initiated on labelx
    PROCESSING = 'processing', 'Processing' #some other third party service is processing the transaction
    FAILED = 'failed', 'Failed' #transaction failed
    SUCCESS = 'success', 'Success' #transaction was successful

class MonthlyPaymentStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    SUCCESS = 'success', 'Success'
    

class WithdrawalRequestInitiatedByChoices(models.TextChoices):
    USER = 'user', 'User'#user tried to withdraw money from their account
    SYSTEM = 'system', 'System'#the system tried to payout the user (used during monthly payment processing)
