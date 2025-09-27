from django.db import models


class TransactionTypeChoices(models.TextChoices):
    WITHDRAWAL = 'withdrawal', 'Withdrawal' #user withdrawing money from their account
    DEPOSIT = 'deposit', 'Deposit' #money was deposited into users account (after labelling a task perhaps)
    MONTHLY_PAYMENT = 'monthly_payment', 'Monthly Payment' #money was credited to the labeller's account for the month

class TransactionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    SUCCESS = 'success', 'Success'

class MonthlyPaymentStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    SUCCESS = 'success', 'Success'
    

class WithdrawalRequestInitiatedByChoices(models.TextChoices):
    USER = 'user', 'User'
    SYSTEM = 'system', 'System'
