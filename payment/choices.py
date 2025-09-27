from django.db import models


class TransactionTypeChoices(models.TextChoices):
    WITHDRAWAL = 'withdrawal', 'Withdrawal' #user withdrawing money from their account
    DEPOSIT = 'deposit', 'Deposit' #money was deposited into users account (after labelling a task perhaps)

class TransactionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    SUCCESS = 'success', 'Success'
    

class WithdrawalRequestInitiatedByChoices(models.TextChoices):
    USER = 'user', 'User'
    SYSTEM = 'system', 'System'
