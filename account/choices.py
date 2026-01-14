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


class StripeConnectAccountStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'#user just generated the connect onboarding link but has not interacted with the link yet
    INITIATED = 'initiated', 'Initiated'#user has started interacting with the connect onboarding link
    COMPLETED = 'completed', 'Completed' # indicates that the user has filled out the onboarding form
    DISABLED = 'disabled', 'Disabled' # indicates that the stripe connect account has been disabled


class ProjectMemberRole(models.TextChoices):
    OWNER = 'owner', 'Owner'
    ADMIN = 'admin', 'Admin'
    MEMBER = 'member', 'Member'
    VIEWER = 'viewer', 'Viewer'


class ProjectInvitationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    EXPIRED = 'expired', 'Expired'
