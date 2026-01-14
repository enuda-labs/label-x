import uuid
from django.contrib.auth.models import AnonymousUser
from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import datetime
import jwt
from cryptography.fernet import Fernet
import base64
import json
from .models import ApiKeyTypeChoices, UserAPIKey, Project, ProjectMember
from rest_framework_api_key.permissions import BaseHasAPIKey

from subscription.models import UserDataPoints, SubscriptionPlan, UserSubscription

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        # Allow read-only access (GET) to all users.
        if request.method in SAFE_METHODS:
            return True

        return request.user != AnonymousUser() and request.user and request.user.is_staff
    

class IsSuperAdmin(BasePermission):
    """Allow access to only users mark as admin"""

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


class IsAdminUser(BasePermission):
    """Allow access to only users mark as admin"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsReviewer(BasePermission):
    """
    Allows access only to users marked as reviewers.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_reviewer
        )

class NotReviewer(BasePermission):
    """
    Restrict access only to users marked as reviewers.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and not request.user.is_reviewer
        )
class HasUserAPIKey(BaseHasAPIKey):
    model = UserAPIKey
    def has_permission(self, request, view):
        has_api_key_permission = super().has_permission(request, view)
        if not has_api_key_permission:
            return False
        
        key = self.get_key(request)
        if not key:
            return False

        api_key = self.model.objects.get_from_key(key)
        request.user = api_key.user
        request.is_test_key = api_key.key_type == ApiKeyTypeChoices.DEVELOPMENT
        return True

def generate_stateless_api_key(user, expiry_days=30):
    """Generates a stateless api key with embedded user information"""
    key_id = str(uuid.uuid4())

    expiry_date = timezone.now() + datetime.timedelta(days=expiry_days)

    payload = {
        "customer_id": str(user.customer_id),
        "username": user.username,
        "key_id": key_id,
        "exp": expiry_date.timestamp(),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"key": token, "expires_at": expiry_date}


def create_api_key_for_uer(user, name="Default", key_type="production"):
    api_key, key = UserAPIKey.objects.create_key(name=name, user=user, key_type=key_type)
    api_key.plain_api_key = key
    api_key.save(update_fields=["plain_api_key"])
    return api_key, key

def assign_default_plan(new_user):
   
    subscription_plan, created = SubscriptionPlan.objects.get_or_create(
        name="free",
        defaults={
            'monthly_fee': 0.0,
            'included_data_points': 50,
            'included_requests': 50,
            'cost_per_extra_request': 0.0,
        }
    )
    expires_at = timezone.now() + timedelta(days=7)
    user_subscription= UserSubscription.objects.create(
        user=new_user,
        plan = subscription_plan,
        expires_at=expires_at,
        renews_at = expires_at,
    )
    user_data_points, created = UserDataPoints.objects.get_or_create(user=new_user)
    user_data_points.topup_data_points(50)


class IsProjectOwnerOrAdmin(BasePermission):
    """Allow access to project creator or users with ADMIN role in the project"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get project_id from view kwargs or request data
        project_id = view.kwargs.get('project_id') or request.data.get('project_id')
        if not project_id:
            return False
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return False
        
        # Check if user is project creator
        if project.created_by == request.user:
            return True
        
        # Check if user has ADMIN or OWNER role
        try:
            member = ProjectMember.objects.get(project=project, user=request.user)
            return member.role in ['admin', 'owner']
        except ProjectMember.DoesNotExist:
            return False


class IsProjectMember(BasePermission):
    """Allow access to any member of the project"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get project_id from view kwargs or request data
        project_id = view.kwargs.get('project_id') or request.data.get('project_id')
        if not project_id:
            return False
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return False
        
        # Check if user is project creator
        if project.created_by == request.user:
            return True
        
        # Check if user is a team member
        return ProjectMember.objects.filter(project=project, user=request.user).exists()


def has_project_permission(user, project, permission):
    """
    Check if user has specific permission in project.
    Permissions: 'create_tasks', 'view_tasks', 'manage_members', 'manage_project'
    """
    if not user or not user.is_authenticated:
        return False
    
    # Project creator has all permissions
    if project.created_by == user:
        return True
    
    try:
        member = ProjectMember.objects.get(project=project, user=user)
        role = member.role
        
        # Permission matrix
        permissions = {
            'owner': ['create_tasks', 'view_tasks', 'manage_members', 'manage_project'],
            'admin': ['create_tasks', 'view_tasks', 'manage_members'],
            'member': ['create_tasks', 'view_tasks'],
            'viewer': ['view_tasks'],
        }
        
        return permission in permissions.get(role, [])
    except ProjectMember.DoesNotExist:
        return False


class HasProjectPermission(BasePermission):
    """Check if user has specific permission in project"""
    
    required_permission = None
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get project_id from view kwargs or request data
        project_id = view.kwargs.get('project_id') or request.data.get('project_id')
        if not project_id:
            return False
        
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return False
        
        permission = getattr(view, 'required_permission', self.required_permission)
        if not permission:
            return False
        
        return has_project_permission(request.user, project, permission)        