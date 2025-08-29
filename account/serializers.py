import re
from rest_framework import serializers
from django.contrib.auth import authenticate

from subscription.models import UserDataPoints, UserSubscription
from subscription.serializers import (
    UserDataPointsSerializer,
    UserSubscriptionSerializer,
    UserSubscriptionSimpleSerializer,
)
from task.choices import TaskClusterStatusChoices
from task.models import Task, TaskCluster, TaskLabel
from django.db.models import Sum, Count


from .models import CustomUser, OTPVerification, Project, ProjectLog


class ProjectLogSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = ProjectLog
        depth = 1


class AdminProjectDetailSerializer(serializers.ModelSerializer):
    cluster_stats = serializers.SerializerMethodField()
    clusters = serializers.SerializerMethodField()

    class Meta:
        fields = "__all__"
        model = Project

    def get_clusters(self, obj):
        from task.serializers import TaskClusterListSerializer
        return TaskClusterListSerializer(TaskCluster.objects.filter(project=obj), many=True).data

    def get_cluster_stats(self, obj):
        clusters = TaskCluster.objects.filter(project=obj)
        assigned_labellers = clusters.aggregate(
            total_labellers=Count("assigned_reviewers")
        )
        total_tasks = clusters.aggregate(total_tasks=Count("tasks"))

        tasks = Task.objects.filter(cluster__in=clusters)

        return {
            "total_clusters": clusters.count(),
            "completed_clusters": clusters.filter(
                status=TaskClusterStatusChoices.COMPLETED
            ).count(),
            "assigned_labellers": assigned_labellers.get("total_labellers", 0),
            "tasks": {
                "total_tasks": total_tasks.get("total_tasks", 0),
                "completed_by_ai": tasks.filter(final_label__isnull=False).count(),
                "completed_by_reviewer": TaskLabel.objects.filter(task__in=tasks)
                .values("task")
                .distinct()
                .count(),
            },
        }


class ProjectDetailSerializer(serializers.ModelSerializer):
    project_logs = serializers.SerializerMethodField()
    user_subscription = serializers.SerializerMethodField()
    user_data_points = serializers.SerializerMethodField()
    task_stats = serializers.SerializerMethodField()

    # total_used_data_points = serializers.SerializerMethodField()
    class Meta:
        fields = "__all__"
        model = Project

    def get_project_logs(self, obj):
        logs = ProjectLog.objects.filter(project=obj)
        return ProjectLogSerializer(logs, many=True).data

    def get_user_data_points(self, obj):
        request = self.context.get("request")
        data_points, created = UserDataPoints.objects.get_or_create(user=request.user)
        return UserDataPointsSerializer(data_points).data

    def get_user_subscription(self, obj):
        request = self.context.get("request")
        if request and request.user:
            try:
                user_subscription = UserSubscription.objects.get(user=request.user)
                return UserSubscriptionSimpleSerializer(user_subscription).data
            except UserSubscription.DoesNotExist:
                return None
        return None

    # def get_total_used_data_points(self, obj):
    #     tasks = Task.objects.filter(group=obj)
    #     total_dp = tasks.aggregate(data_points=Sum('used_data_points'))
    #     return total_dp.get('data_points', 0)

    def get_task_stats(self, obj):
        tasks = Task.objects.filter(group=obj)

        completed_tasks = tasks.filter(processing_status="COMPLETED").count()
        total_data_points = tasks.aggregate(data_points=Sum("used_data_points"))

        total_tasks = tasks.count()
        completion_percentage = (
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        )

        print(total_data_points)
        return {
            "completion_percentage": round(completion_percentage, 2),
            "total_used_data_points": total_data_points.get("data_points", 0) or 0,
        }


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class Disable2faSerializer(serializers.Serializer):
    password = serializers.CharField()


class OtpVerificationSerializer(serializers.ModelSerializer):
    otp_code = serializers.CharField(write_only=True)

    class Meta:
        model = OTPVerification
        fields = ["otp_code", "is_verified"]
        read_only_fields = ["is_verified"]

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
        fields = [
            "id",
            "username",
            "email",
            "is_reviewer",
            "is_admin",
            "roles",
            "permissions",
        ]

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
            permissions.extend(
                [
                    "can_manage_users",
                    "can_manage_projects",
                    "can_manage_subscriptions",
                    "can_manage_api_keys",
                    "can_review_tasks",
                    "can_create_tasks",
                    "can_view_all_tasks",
                ]
            )
        elif obj.is_admin:
            permissions.extend(
                [
                    "can_manage_reviewers",
                    "can_manage_projects",
                    "can_review_tasks",
                    "can_create_tasks",
                    "can_view_all_tasks",
                ]
            )
        elif obj.is_reviewer:
            permissions.extend(["can_review_tasks", "can_view_assigned_tasks"])
        else:
            permissions.extend(["can_create_tasks", "can_view_own_tasks"])
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
    role = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "password", "role"]
        extra_kwargs = {
            "username": {"error_messages": {"unique": "Username already exists"}},
            "email": {"error_messages": {"unique": "Email already exists"}},
        }

    def create(self, validated_data):
        # Pop the password and role from validated_data
        password = validated_data.pop("password")
        role = validated_data.pop("role")

        # Create user instance
        user = CustomUser.objects.create(**validated_data)

        # Set the password (this will hash it)
        user.set_password(password)
        user.save()

        return user, role

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
        fields = ["id", "name", "description"]


class UserProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "created_by", "description", "created_at", "status"]
        read_only_fields = ["created_by", "created_at"]

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
        fields = ["id", "username", "email", "is_active"]


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


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change endpoint"""

    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    confirm_password = serializers.CharField(required=True, min_length=8)

    def validate(self, data):
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "The two password fields didn't match."}
            )
        return data


class UpdateNameSerializer(serializers.Serializer):
    """Serializer for name update endpoint"""

    username = serializers.CharField(required=True, max_length=255)

    def validate_username(self, value):
        user = self.context["request"].user
        if CustomUser.objects.exclude(pk=user.pk).filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


class ProjectSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "members",
            "created_at",
            "updated_at",
            "status",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_created_by(self, obj):
        if obj.created_by is None:
            return None
        return {
            "id": obj.created_by.id,
            "username": obj.created_by.username,
            "email": obj.created_by.email,
        }

    def get_members(self, obj):
        return [
            {"id": member.id, "username": member.username, "email": member.email}
            for member in obj.members.all()
        ]
