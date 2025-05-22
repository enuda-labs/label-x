import re
from rest_framework import serializers
from django.contrib.auth import authenticate


from .models import CustomUser, OTPVerification, Project


class OtpVerificationSerializer(serializers.ModelSerializer):
    otp_code = serializers.CharField(write_only=True)
    
    class Meta:
        model = OTPVerification
        fields = ['otp_code', 'is_verified']
        read_only_fields = ['is_verified']
        
    def validate(self, attrs):
        otp_code = attrs.pop("otp_code")
        if not self.instance.verify_otp(otp_code):
            raise serializers.ValidationError("Invalid otp code")
        return attrs
    
    
class UserSerializer(serializers.ModelSerializer):
    """Serializer for the user model"""
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "is_reviewer", "is_admin", "roles", "permissions"]

    def get_roles(self, obj):
        roles = []
        if obj.is_superuser:
            roles.append("superuser")
        if obj.is_admin & obj.is_staff:
            roles.append("admin")
        if obj.is_reviewer:
            roles.append("reviewer")
        
        return roles

    def get_permissions(self, obj):
        permissions = []
        if obj.is_superuser:
            permissions.extend([
                "can_manage_users",
                "can_manage_projects",
                "can_manage_subscriptions",
                "can_manage_api_keys",
                "can_review_tasks",
                "can_create_tasks",
                "can_view_all_tasks"
            ])
        elif obj.is_admin:
            permissions.extend([
                "can_manage_reviewers",
                "can_manage_projects",
                "can_review_tasks",
                "can_create_tasks",
                "can_view_all_tasks"
            ])
        elif obj.is_reviewer:
            permissions.extend([
                "can_review_tasks",
                "can_view_assigned_tasks"
            ])
        else:
            permissions.extend([
                "can_create_tasks",
                "can_view_own_tasks"
            ])
        return permissions


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    otp_code = serializers.CharField(required=False)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        print(user)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User is not active")
        return user


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "password"]
        extra_kwargs = {
            "username": {"error_messages": {"unique": "Username already exists"}},
            "email": {"error_messages": {"unique": "Email already exists"}},
        }

    def create(self, validated_data):
        # Pop the password from validated_data
        password = validated_data.pop("password")

        # Create user instance
        user = CustomUser.objects.create(**validated_data)

        # Set the password (this will hash it)
        user.set_password(password)
        user.save()

        return user

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_password(self, value):
        """
        Validate password with detailed error messages for specific requirements
        """
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            )
        if not re.search(r"[A-Z]", value):
            raise serializers.ValidationError(
                "Password must contain at least one uppercase letter"
            )
        if not re.search(r"[a-z]", value):
            raise serializers.ValidationError(
                "Password must contain at least one lowercase letter"
            )
        if not re.search(r"\d", value):
            raise serializers.ValidationError(
                "Password must contain at least one number"
            )
        if not re.search(r"[@$!%*?&]", value):
            raise serializers.ValidationError(
                "Password must contain at least one special character (@$!%*?&)"
            )
        return value


class MakeReviewerSerializer(serializers.Serializer):
    """serializer to make a user a reviewer"""

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), help_text="ID of the user to promote"
    )
    group_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        help_text="ID of the project group to assign the user to",
    )


class RevokeReviewerSerializer(serializers.Serializer):
    """Serializer to remove a user from being a reviewer"""

    user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(), help_text="ID of the reviewer to revoke"
    )


class MakeAdminSerializer(serializers.Serializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        help_text="ID of the user to promote to admin",
    )


class TokenRefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        help_text="The refresh token to obtain a new access token."
    )


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="The new access token.")
    refresh = serializers.CharField(help_text="The new refresh token.", required=False)


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", 'description']
        

class UserProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "created_by", "description", 'created_at']
        read_only_fields = ["created_by", 'created_at']

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "is_reviewer",
            "is_admin",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_activity",
        ]


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
        ]


# Set of Serializers to use for api doc example and documentation
# ==============================================================
class SuccessDetailResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()


class UserDetailResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    user = UserDetailSerializer()


class UserListResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    users = SimpleUserSerializer(many=True)


class ProjectListResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    projects = ProjectCreateSerializer(many=True)
