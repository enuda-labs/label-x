from django.db import models


class ProjectStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = 'in_progress', "In progress"
    COMPLETED = 'completed', 'Completed'


class BankPlatformChoices(models.TextChoices):
    PAYSTACK = 'paystack', 'Paystack'
    STRIPE = 'stripe', 'Stripe'
    
class MonthlyEarningsReleaseStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'#indicates there has not been an attempt to release the earnings to the reviewer
    INITIATED = 'initiated', 'Initiated'#indicates that a transfer has been initiated, and we are waiting for paystack or any other payment provider to complete the transfer
    RELEASED = 'released', 'Released'#indicates that the earnings have been released to the reviewer
    FAILED = 'failed', 'Failed'#indicates that the attempt to release the earnings to the reviewer failed
