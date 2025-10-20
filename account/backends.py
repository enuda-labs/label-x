from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user= User.objects.filter(Q(email=username) | Q(username=username)).first()
        if not user:
            return None
        
        if not user.check_password(password):
            return None
        
        if not user.is_active:
            return None
        
        return user
        