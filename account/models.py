import decimal
from email import message
from io import BytesIO
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Avg
from django.db.models import F
import pyotp
import qrcode
from rest_framework_api_key.models import AbstractAPIKey
from django.core.files.base import ContentFile
from cloudinary.models import CloudinaryField
import cloudinary.uploader

from account.choices import ProjectStatusChoices
from payment.choices import TransactionStatusChoices, TransactionTypeChoices
from reviewer.models import LabelerDomain
from task.choices import TaskInputTypeChoices


class Project(models.Model):
    """Group that reviewers belong to"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey('CustomUser', related_name='tasks', blank=True, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=ProjectStatusChoices.choices, default=ProjectStatusChoices.PENDING)

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


class CustomUserManager(BaseUserManager):
    """Manager for custom user model"""
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required')
        if not email:
            raise ValueError('Email is required')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None):
        user = self.create_user(username, email, password)
        user.is_staff = True
        user.is_admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user
    


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """Custom User model that uses username and email for authentication"""
    username = models.CharField(max_length=255, unique=True)
    pid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_reviewer = models.BooleanField(default=False, help_text="Designates whether this user can review tasks")
    is_admin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True, help_text="Last time the user was active")
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False) 
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, related_name='members', null=True, blank=True)
    domains = models.ManyToManyField(LabelerDomain, related_name='labelers', blank=True, help_text="The domains of expertise that the labeler is allowed to label")

    objects = CustomUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username



class LabelerEarnings(models.Model):
    id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, primary_key=True)
    labeler = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='labeler_earnings')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="The balance of the labeler in USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Balance for {self.labeler.username}"
    
    def deduct_balance(self, usd_amount, reason=None, create_transaction=True):
        from payment.models import Transaction

        self.balance = F('balance') - decimal.Decimal(usd_amount)
        self.save(update_fields=['balance'])
        self.refresh_from_db()
        
        if create_transaction:
            Transaction.objects.create(
                user=self.labeler,
                usd_amount=usd_amount,
                transaction_type=TransactionTypeChoices.WITHDRAWAL,
                description=reason,
                status=TransactionStatusChoices.SUCCESS,
            )
        return self.balance
    
    def topup_balance(self, usd_amount, reason=None, create_transaction=True):
        from payment.models import Transaction

        self.balance = F('balance') + decimal.Decimal(usd_amount)
        self.save(update_fields=['balance'])
        self.refresh_from_db()
        
        if create_transaction:
            Transaction.objects.create(
                user=self.labeler,
                usd_amount=usd_amount,
                transaction_type=TransactionTypeChoices.DEPOSIT,
                description=reason,
                status=TransactionStatusChoices.SUCCESS,
            )
        return self.balance

class ApiKeyTypeChoices(models.TextChoices):
    PRODUCTION = 'production', 'Production',
    TEST = 'test', 'Test'

class UserAPIKey(AbstractAPIKey):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="api_keys"
    )
    key_type = models.CharField(choices=ApiKeyTypeChoices.choices, default=ApiKeyTypeChoices.PRODUCTION, max_length=20)
    plain_api_key = models.CharField(max_length=255, null=True, blank=True)
    

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "User API key"
        verbose_name_plural = "User API keys"
    
    
class OTPVerification(models.Model):
    user= models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='otp')
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
        
        result = cloudinary.uploader.upload(
            buffer,
            folder="qr_codes",
            public_id=f"{self.user.id}_qr_code",
            overwrite=True,
            resource_type="image"
        )
        
        
        # self.qr_code.save(
        #     f"{self.user.id}_qr_code.png",
        #     ContentFile(buffer.read()),
        #     save=False)
        self.qr_code = result["secure_url"]
        self.cloudinary_data = result
        
    def verify_otp(self, otp_code):
        totp = pyotp.TOTP(self.secret_key)
        return totp.verify(otp_code)
        
