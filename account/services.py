import random
import logging
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from account.models import User

logger = logging.getLogger(__name__)

class EmailService():
    def __init__(self, email:str, name:str=None) -> None:
        self.email=email
        self.name=name
    
    def send_template_email(self, subject, template_path:str, context:dict):
        """Send email using Django's send_mail with django-anymail (Resend backend)"""
        html_message = render_to_string(template_path, context)
        try:
            send_mail(
                subject=subject,
                message="",  # Plain text version (empty, using HTML only)
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Email sent successfully to '{self.email}' with subject '{subject}'")
            return True
        except Exception as e:
            logger.error(f"Error sending email to '{self.email}': {str(e)}", exc_info=True)
            return False

def generate_code(length=6):
    return "".join([str(random.randint(0, 9)) for _ in range(length)])

def generate_and_save_otp(email, length=6, timeout=300):
    otp = generate_code(length=length)
    
    cache.set(email, otp, timeout)
    return otp

def send_account_verification_email(user:User):
    email_service = EmailService(user.email)
    otp = generate_and_save_otp(f"vrf-{user.email}")
    email_service.send_template_email(
        subject="Account Verification",
        template_path="account_vrf.html",
        context={
            "otp": otp,
            "user": user
        }
    )


def send_password_reset_email(user: User):
    otp = generate_and_save_otp(f"pr-{user.email}")
    email_service = EmailService(user.email)
    email_service.send_template_email(
        subject="Reset your Labelx account password",
        template_path="password_reset.html",
        context={
            "otp": otp,
            "user": user
        }
    )


def verify_password_reset_otp(email, user_otp):
    cached_otp = cache.get(f"pr-{email}")

    user = get_user_by_email(email)
    if not user:
        return False, "Invalid user account"

    if cached_otp and user:
        if user_otp == cached_otp:
            return (
                True,
                "Valid otp",
            )
        else:
            return False, "Invalid or expired otp"

    return False, "Invalid or expired otp"


def get_user_by_email(email) -> User:
    try:
        user = User.objects.get(email=email)
        return user
    except User.DoesNotExist:
        return None
    
    # otp = generate_and_save_otp(email)
    