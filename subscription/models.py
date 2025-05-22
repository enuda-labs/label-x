from datetime import timezone
from django.db import models
from account.models import CustomUser


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = (
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    )
    name = models.CharField(max_length=50, choices=PLAN_CHOICES, unique=True)
    monthly_fee = models.DecimalField(max_digits=8, decimal_places=2)
    included_requests = models.IntegerField()  # number of included API calls
    cost_per_extra_request = models.DecimalField(max_digits=6, decimal_places=4)
    stripe_monthly_plan_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name

    def __str__(self):
        return f"{self.name} (${self.monthly_fee})"


class Wallet(models.Model):
    """wallet for storing the user balance from which
    the deduction will take place with a task is created.
    """

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user.username}'s Wallet: ${self.balance}"


class UserSubscription(models.Model):
    """model to keep tranction of the subscription plan a user has subscribe to."""

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    requests_used = models.IntegerField(default=0)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    renews_at = models.DateTimeField()

    def is_active(self):
        return self.expires_at and self.expires_at > timezone.now()


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default="pending")  # success, failed
    created_at = models.DateTimeField(auto_now_add=True)


class UserPaymentStatus(models.TextChoices):
    PENDING = "Pending", "pending"
    FAILED = "Failed", "failed"
    SUCCESS = "Success", "success"


class UserPaymentHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=30, decimal_places=4)
    description = models.CharField(max_length=255)
    status = models.CharField(
        max_length=10,
        choices=UserPaymentStatus.choices,
        default=UserPaymentStatus.PENDING,
    )
    payment_url = models.TextField(null=True, blank=True)
