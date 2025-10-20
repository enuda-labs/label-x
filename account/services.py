import random
from django.core.cache import cache
import requests
from django.conf import settings
from django.template.loader import render_to_string
from account.models import CustomUser

class EmailService():
    def __init__(self, email:str, name:str=None) -> None:
        self.email=email
        self.name=name
        
    def _send_brevo_email(self, subject, html_content):
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.BREVO_API_KEY}", # this is the api key for the brevo api
                "accept": "application/json",
                "api-key": settings.BREVO_API_KEY
            },
            json={
                "to": [{"email": self.email}],
                "subject": subject,
                "htmlContent": html_content,
                "sender": {
                    "name": "Labelx",
                    # "email": "support@erdvsion.dev"
                    "email": settings.BREVO_FROM_EMAIL
                }
            }
        )
        try:
            return response.json()
        except Exception as e:
            print(e)
            return None
    
    def send_raw_email(self, subject, message):
        pass
    
    def send_template_email(self, subject, template_path:str, context:dict):
        html_message = render_to_string(template_path, context)
        return self._send_brevo_email(subject, html_message)

def generate_code(length=6):
    return "".join([str(random.randint(0, 9)) for _ in range(length)])

def generate_and_save_otp(email, length=6, timeout=300):
    otp = generate_code(length=length)
    
    cache.set(email, otp, timeout)
    return otp

def send_account_verification_email(user:CustomUser):
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


def send_password_reset_email(user: CustomUser):
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


def get_user_by_email(email) -> CustomUser:
    try:
        user = CustomUser.objects.get(email=email)
        return user
    except CustomUser.DoesNotExist:
        return None
    
    # otp = generate_and_save_otp(email)
    