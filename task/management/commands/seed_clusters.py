from typing import Any
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from account.models import Project
from subscription.models import SubscriptionPlan, UserDataPoints, UserSubscription
from task.models import TaskCluster
from task.choices import TaskTypeChoices, TaskInputTypeChoices, AnnotationMethodChoices

User = get_user_model()


class Command(BaseCommand):
    help = "Seed sample clusters for projects"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Username to create clusters for (if not provided, will use first superuser or create test user)",
        )
        parser.add_argument(
            "--project-name",
            type=str,
            default=None,
            help="Name of the project to create clusters in (if not provided, will use first project or create one)",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of clusters to create (default: 5)",
        )
        parser.add_argument(
            "--task-type",
            type=str,
            choices=["TEXT", "IMAGE", "VIDEO", "AUDIO", "CSV"],
            default=None,
            help="Type of tasks in clusters (if not provided, will create a mix)",
        )
        parser.add_argument(
            "--annotation-method",
            type=str,
            choices=["manual", "ai_automated"],
            default="manual",
            help="Annotation method for clusters (default: manual)",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        username = options.get("username")
        project_name = options.get("project_name")
        cluster_count = options.get("count")
        task_type = options.get("task_type")
        annotation_method = options.get("annotation_method")

        # Get or create user
        user = None
        if username:
            try:
                user = User.objects.get(username=username)
                self.stdout.write(self.style.SUCCESS(f"Using existing user: {username}"))
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User '{username}' not found. Please create the user first.")
                )
                return
        else:
            # Try to get first superuser
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                # Try to get first staff user
                user = User.objects.filter(is_staff=True).first()
            if not user:
                # Create a test user
                user = User.objects.create_user(
                    username="testuser",
                    email="testuser@example.com",
                    password="TestP@ssword123!",
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created test user: {user.username}")
                )

        # Ensure user has subscription and data points
        plan, _ = SubscriptionPlan.objects.get_or_create(
            name="starter",
            defaults={
                "monthly_fee": 10.00,
                "included_data_points": 10000,
                "included_requests": 100,
                "cost_per_extra_request": 7,
            },
        )

        user_data_points, _ = UserDataPoints.objects.get_or_create(user=user)
        if user_data_points.data_points_balance < 1000:
            user_data_points.topup_data_points(10000)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Topped up data points for {user.username}: {user_data_points.data_points_balance}"
                )
            )

        expires_at = timezone.now() + timedelta(days=30)
        UserSubscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": plan,
                "renews_at": expires_at,
                "expires_at": expires_at,
            },
        )

        # Get or create project
        if project_name:
            project, created = Project.objects.get_or_create(
                name=project_name,
                defaults={
                    "description": f"Sample project for testing clusters",
                    "created_by": user,
                },
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created project: {project_name}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Using existing project: {project_name}")
                )
        else:
            # Use first project or create one
            project = Project.objects.first()
            if not project:
                project = Project.objects.create(
                    name="Sample Project",
                    description="Sample project for testing clusters",
                    created_by=user,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created project: {project.name}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Using existing project: {project.name}")
                )

        # Ensure project has created_by set
        if not project.created_by:
            project.created_by = user
            project.save()

        # Task types to create (mix if not specified)
        task_types = (
            [task_type] if task_type else ["TEXT", "IMAGE", "VIDEO", "AUDIO", "CSV"]
        )

        # Create clusters
        created_count = 0
        for i in range(cluster_count):
            # Cycle through task types if creating multiple clusters
            current_task_type = task_types[i % len(task_types)]
            
            # Determine input type based on task type
            if current_task_type == "TEXT":
                input_type = TaskInputTypeChoices.TEXT
            elif current_task_type in ["IMAGE", "VIDEO", "AUDIO"]:
                input_type = TaskInputTypeChoices.IMAGE
            else:
                input_type = TaskInputTypeChoices.TEXT

            cluster_name = f"Sample {current_task_type} Cluster {i + 1}"
            
            # Check if cluster already exists
            if TaskCluster.objects.filter(name=cluster_name, project=project).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Cluster '{cluster_name}' already exists, skipping..."
                    )
                )
                continue

            cluster = TaskCluster.objects.create(
                name=cluster_name,
                project=project,
                description=f"Sample cluster for {current_task_type} tasks - Batch {i + 1}",
                task_type=current_task_type,
                input_type=input_type,
                labeller_instructions=f"Please review and label these {current_task_type.lower()} tasks carefully. Follow the guidelines provided.",
                annotation_method=annotation_method,
                labeller_per_item_count=3,
                created_by=user,
                deadline=timezone.now().date() + timedelta(days=7),  # 7 days from now
            )

            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created cluster: {cluster_name} (ID: {cluster.id})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Successfully created {created_count} cluster(s) in project '{project.name}'"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"   Project: {project.name} (ID: {project.id})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"   User: {user.username} (ID: {user.id})")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"   Total clusters in project: {project.clusters.count()}"
            )
        )

