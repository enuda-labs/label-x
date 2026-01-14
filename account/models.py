import decimal
from email import message
from io import BytesIO
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Avg
from django.db.models import F
import pyotp
import qrcode
from rest_framework_api_key.models import AbstractAPIKey
from cloudinary.models import CloudinaryField
import cloudinary.uploader

from account.choices import (
    BankPlatformChoices, 
    MonthlyEarningsReleaseStatusChoices, 
    ProjectStatusChoices,
    ProjectMemberRole,
    ProjectInvitationStatus,
    StripeConnectAccountStatusChoices
)
from reviewer.models import LabelerDomain


class Project(models.Model):
    """Group that reviewers belong to"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey('User', related_name='tasks', blank=True, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=ProjectStatusChoices.choices, default=ProjectStatusChoices.PENDING)
    team_members = models.ManyToManyField('User', through='ProjectMember', related_name='team_projects', blank=True)

    def get_cluster_label_completion_percentage(self):
        completion_percentage = self.clusters.aggregate(completion_percentage=Avg("completion_percentage"))["completion_percentage"]
        return completion_percentage
    
    def create_log(self, message, task=None):
        return ProjectLog.objects.create(project=self, message=message, task=task)
    

    def __str__(self):
        return self.name
    
    class Meta:
        ordering= ['-created_at']


class ProjectLog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    task = models.ForeignKey("task.Task", on_delete=models.CASCADE, null=True, blank=True, help_text="Null if this log is not related to a specific task/annotation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    message= models.TextField()
    
    def __str__(self) -> str:
        return self.message


class User(AbstractUser):
    """User model extending Django's AbstractUser"""
    customer_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_reviewer = models.BooleanField(default=False, help_text="Designates whether this user can review tasks")
    last_activity = models.DateTimeField(auto_now=True, help_text="Last time the user was active")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, related_name='reviewer_members', null=True, blank=True, help_text="Project assignment for reviewers (legacy field)")
    domains = models.ManyToManyField(LabelerDomain, related_name='labelers', blank=True, help_text="The domains of expertise that the labeler is allowed to label")
    is_email_verified = models.BooleanField(default=False, help_text="Indicates if the email of the user has been verified")

    def __str__(self):
        return self.username
    

class UserBankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bank_accounts')
    account_number = models.CharField(max_length=255)
    bank_code = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    account_name = models.CharField(max_length=255, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    platform = models.CharField(max_length=255, choices=BankPlatformChoices.choices, default=BankPlatformChoices.PAYSTACK, help_text="The platform of the bank account, e.g. paystack, flutterwave, etc.")
    
    def __str__(self):
        return f"{self.user.username}'s bank account - {self.bank_name} account number {self.account_number}"

class UserStripeConnectAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stripe_connect_account')
    account_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=255, choices=StripeConnectAccountStatusChoices.choices, default=StripeConnectAccountStatusChoices.PENDING, help_text="The status of the stripe connect account")
    payouts_enabled = models.BooleanField(default=False, help_text="Indicates if the stripe connect account has payouts enabled")
    
    def __str__(self):
        return f"{self.user.username}'s stripe connect account - {self.account_id}"
    
    class Meta:
        indexes = [
            models.Index(fields=['account_id']),
        ]

class MonthlyReviewerEarnings(models.Model):
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE)
    year = models.IntegerField() #a year e.g 2025
    month = models.IntegerField() #a month e.g 1 for January and 12 for December
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_earnings_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0, help_text="The total earnings of the reviewer in USD for this month")
    usd_balance = models.DecimalField(max_digits=10, decimal_places=4, default=0, help_text="The balance of the reviewer in USD")
    release_status = models.CharField(max_length=50, choices=MonthlyEarningsReleaseStatusChoices.choices, default=MonthlyEarningsReleaseStatusChoices.PENDING, help_text="Indicates if the earnings for this month has been released to the reviewer")
    
    def topup_balance(self, usd_amount, increment_total_earnings=True):
        amount = decimal.Decimal(usd_amount)
        self.usd_balance = F('usd_balance') + amount
        if increment_total_earnings:
            self.total_earnings_usd = F('total_earnings_usd') + amount
        self.save(update_fields=['usd_balance', 'total_earnings_usd'])
        return self.usd_balance
    
    def deduct_balance(self, usd_amount):
        amount = decimal.Decimal(usd_amount)
        self.usd_balance = F('usd_balance') - amount
        self.save(update_fields=['usd_balance'])
        return self.usd_balance
    
    def __str__(self):
        return f"{self.reviewer.username} - {self.month} - {self.year}"

class ApiKeyTypeChoices(models.TextChoices):
    PRODUCTION = 'production', 'Production',
    TEST = 'test', 'Test'

class UserAPIKey(AbstractAPIKey):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="api_keys"
    )
    key_type = models.CharField(choices=ApiKeyTypeChoices.choices, default=ApiKeyTypeChoices.PRODUCTION, max_length=20)
    plain_api_key = models.CharField(max_length=255, null=True, blank=True)
    

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "User API key"
        verbose_name_plural = "User API keys"
    
    
class OTPVerification(models.Model):
    user= models.OneToOneField(User, on_delete=models.CASCADE, related_name='otp')
    secret_key = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    # qr_code = models.ImageField(upload_to="qr_codes/", blank=True, null=True)    
    qr_code = CloudinaryField("image", null=True, blank=True)    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cloudinary_data = models.JSONField(null=True, blank=True, help_text="The full result from gotten when uploading the image to cloudinary")
    
    def __str__(self) -> str:
        return f"Otp for {self.user.email}"
    
    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = pyotp.random_base32()
            self.generate_qr_code()
        super().save(*args, **kwargs)
    
    
    def generate_qr_code(self):
        """Generate qr code for otp verification"""
        import base64
        from django.conf import settings
        
        totp = pyotp.totp.TOTP(self.secret_key).provisioning_uri(
            name=self.user.email,
            issuer_name="Label x"
        )
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(totp)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Try to upload to Cloudinary if properly configured, otherwise use data URL
        cloudinary_configured = (
            settings.CLOUDINARY_CLOUD_NAME and 
            settings.CLOUDINARY_API_KEY and 
            settings.CLOUDINARY_API_SECRET and
            'example' not in settings.CLOUDINARY_CLOUD_NAME.lower()  # Skip if using placeholder
        )
        
        if cloudinary_configured:
            try:
                # Use a short timeout to fail fast if Cloudinary is unreachable
                result = cloudinary.uploader.upload(
                    buffer,
                    folder="qr_codes",
                    public_id=f"{self.user.id}_qr_code",
                    overwrite=True,
                    resource_type="image",
                    timeout=5  # 5 second timeout to fail fast
                )
                self.qr_code = result["secure_url"]
                self.cloudinary_data = result
                return
            except Exception as e:
                # If Cloudinary upload fails, fall back to data URL immediately
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Cloudinary upload failed for 2FA QR code: {e}. Falling back to data URL.")
                buffer.seek(0)  # Reset buffer position
        
        # Fallback: Generate data URL
        buffer.seek(0)
        img_data = buffer.read()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        self.qr_code = f"data:image/png;base64,{img_base64}"
        self.cloudinary_data = None
        
    def verify_otp(self, otp_code):
        totp = pyotp.TOTP(self.secret_key)
        return totp.verify(otp_code)


class ProjectMember(models.Model):
    """Team member relationship between User and Project with role"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='project_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=20, choices=ProjectMemberRole.choices, default=ProjectMemberRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['project', 'user']]
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user.username} - {self.project.name} ({self.role})"


class ProjectInvitation(models.Model):
    """Email invitation for project membership"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ProjectMemberRole.choices, default=ProjectMemberRole.MEMBER)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=ProjectInvitationStatus.choices, default=ProjectInvitationStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = [['project', 'email', 'status']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['email', 'status']),
        ]

    def __str__(self):
        return f"Invitation for {self.email} to {self.project.name} ({self.status})"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def accept(self, user):
        """Accept invitation and create ProjectMember"""
        if self.status != ProjectInvitationStatus.PENDING:
            raise ValueError("Invitation is not pending")
        if self.is_expired():
            self.status = ProjectInvitationStatus.EXPIRED
            self.save()
            raise ValueError("Invitation has expired")
        
        # Create project member
        ProjectMember.objects.get_or_create(
            project=self.project,
            user=user,
            defaults={'role': self.role}
        )
        self.status = ProjectInvitationStatus.ACCEPTED
        self.save()
        
