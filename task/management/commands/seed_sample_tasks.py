from typing import Any
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from account.models import Project
from subscription.models import SubscriptionPlan, UserDataPoints, UserSubscription
from task.models import Task, TaskCluster
from task.choices import TaskTypeChoices, TaskInputTypeChoices, AnnotationMethodChoices

User = get_user_model()


class Command(BaseCommand):
    help = "Seed sample tasks for testing the labelling feature"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=None,
            help="Username to create tasks for (if not provided, will use first superuser or create test user)",
        )
        parser.add_argument(
            "--project-name",
            type=str,
            default="Sample Project",
            help="Name of the project to create tasks in (default: 'Sample Project')",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of sample tasks to create (default: 10)",
        )
        parser.add_argument(
            "--task-type",
            type=str,
            choices=["TEXT", "IMAGE", "VIDEO", "AUDIO", "CSV"],
            default="TEXT",
            help="Type of tasks to create (default: TEXT)",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        username = options.get("username")
        project_name = options.get("project_name")
        task_count = options.get("count")
        task_type = options.get("task_type")

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
        project, created = Project.objects.get_or_create(
            name=project_name,
            defaults={
                "description": f"Sample project for testing tasks",
                "created_by": user,
            },
        )
        # Ensure created_by is set even if project already exists
        if not project.created_by:
            project.created_by = user
            project.save()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created project: {project_name}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Using existing project: {project_name}")
            )

        # Create task cluster
        cluster_name = f"Sample {task_type} Cluster"
        cluster, created = TaskCluster.objects.get_or_create(
            name=cluster_name,
            project=project,
            defaults={
                "description": f"Sample cluster for {task_type} tasks",
                "task_type": task_type,
                "input_type": TaskInputTypeChoices.TEXT
                if task_type == "TEXT"
                else TaskInputTypeChoices.IMAGE,
                "labeller_instructions": "Please review and label these sample tasks.",
                "annotation_method": AnnotationMethodChoices.AI_AUTOMATED,
                "labeller_per_item_count": 3,
                "created_by": user,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created cluster: {cluster_name}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Using existing cluster: {cluster_name}")
            )

        # Sample data for different task types
        # Using publicly available sample data URLs
        sample_data = {
            "TEXT": [
                "This is a positive review of our product.",
                "I hate this service, it's terrible!",
                "The weather is nice today.",
                "Please review this content for moderation.",
                "This is a neutral statement with no sentiment.",
                "Amazing product! Highly recommended!",
                "I'm not sure about this.",
                "This content needs careful review.",
                "Great service and excellent support.",
                "This is inappropriate content.",
                "The customer service was outstanding and very helpful.",
                "This product exceeded my expectations in every way.",
                "I would not recommend this to anyone.",
                "The quality is decent but could be better.",
                "Outstanding value for money, highly satisfied!",
            ],
            "IMAGE": [
                "https://picsum.photos/800/600?random=1",
                "https://picsum.photos/800/600?random=2",
                "https://picsum.photos/800/600?random=3",
                "https://picsum.photos/800/600?random=4",
                "https://picsum.photos/800/600?random=5",
                "https://picsum.photos/800/600?random=6",
                "https://picsum.photos/800/600?random=7",
                "https://picsum.photos/800/600?random=8",
                "https://picsum.photos/800/600?random=9",
                "https://picsum.photos/800/600?random=10",
                "https://via.placeholder.com/800x600/FF5733/FFFFFF?text=Sample+Image+1",
                "https://via.placeholder.com/800x600/33FF57/FFFFFF?text=Sample+Image+2",
                "https://via.placeholder.com/800x600/3357FF/FFFFFF?text=Sample+Image+3",
                "https://via.placeholder.com/800x600/FF33F5/FFFFFF?text=Sample+Image+4",
                "https://via.placeholder.com/800x600/F5FF33/FFFFFF?text=Sample+Image+5",
            ],
            "VIDEO": [
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyrides.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackOnStreetAndDirt.mp4",
                "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
            ],
            "AUDIO": [
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-9.mp3",
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3",
            ],
            "CSV": [
                "https://people.sc.fsu.edu/~jburkardt/data/csv/addresses.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/cities.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/crash_catalonia.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/deniro.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/freshman_lbs.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/gradebook.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/hw_200.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/lead_shot.csv",
                "https://people.sc.fsu.edu/~jburkardt/data/csv/mn.csv",
            ],
        }

        # Create tasks
        data_list = sample_data.get(task_type, sample_data["TEXT"])
        created_count = 0

        for i in range(task_count):
            data = data_list[i % len(data_list)]
            
            # For non-TEXT tasks, we need to set file-related fields
            if task_type != "TEXT":
                # Extract file info from URL
                file_url = data
                file_name = file_url.split("/")[-1].split("?")[0]
                file_type = file_name.split(".")[-1] if "." in file_name else "unknown"
                
                task = Task.objects.create(
                    cluster=cluster,
                    user=user,
                    group=project,
                    task_type=task_type,
                    data="",  # Empty for non-text tasks
                    file_url=file_url,
                    file_name=file_name,
                    file_type=file_type,
                    file_size_bytes=1024 * 100,  # Default 100KB
                    priority="NORMAL",
                    processing_status="PENDING",
                    used_data_points=0,
                )
            else:
                task = Task.objects.create(
                    cluster=cluster,
                    user=user,
                    group=project,
                    task_type=task_type,
                    data=data,
                    priority="NORMAL",
                    processing_status="PENDING",
                    used_data_points=0,
                )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Successfully created {created_count} {task_type} task(s) in cluster '{cluster_name}'"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"   Project: {project_name} (ID: {project.id})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"   Cluster: {cluster_name} (ID: {cluster.id})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"   User: {user.username} (ID: {user.id})")
        )

