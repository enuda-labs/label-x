from rest_framework.permissions import BasePermission

class IsSuperAdmin(BasePermission):
    """Allow access to only users mark as admin"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser
    

class IsAdminUser(BasePermission):
    """Allow access to only users mark as admin"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin
    

class IsReviewer(BasePermission):
    """
    Allows access only to users marked as reviewers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_reviewer)
