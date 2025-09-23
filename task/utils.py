from celery import Task, shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db import models
from django.utils import timezone
from datetime import timedelta
from task.choices import TaskClusterStatusChoices, TaskTypeChoices
from account.models import CustomUser
import math
from task.models import TaskCluster
from common.utils import get_dp_cost_settings
import random
from django.db.models import Count, Q
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Count, Sum
from account.models import LabelerEarnings


def serialize_task(task):
    from task.serializers import FullTaskSerializer

    return FullTaskSerializer(task).data


def dispatch_task_message(receiver_id, payload, action="notification"):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_tasks_{receiver_id}",
        {"type": "task.message", "text": {"action": action, **payload}},
    )
    print("dispatched ws message")


def dispatch_review_response_message(receiver_id, payload):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"reviewer_group_{receiver_id}",
        {"type": "response.message", "text": {"action": "review_response", **payload}},
    )
    print("dispatched ws message")    


def push_realtime_update(task: Task, action="notification"):
    serialized = serialize_task(task)
    if task.user:
        dispatch_task_message(task.user.id, serialized, action=action)


def assign_reviewer(task):
    """
    Assigns a reviewer to a task based on availability and workload.
    Returns True if a reviewer was assigned, False otherwise.
    """
    # Get all online reviewers who have been active in the last 5 minutes
    # Annotate with pending review count for efficient sorting
    active_reviewers = (
        CustomUser.objects.filter(
            is_reviewer=True,
            is_online=True,
            last_activity__gte=timezone.now() - timedelta(minutes=20),
        )
        .annotate(
            pending_count=models.Count(
                "assigned_tasks",
                filter=models.Q(assigned_tasks__status="REVIEW_NEEDED"),
            )
        )
        .order_by("pending_count")
    )

    if not active_reviewers.exists():
        return False

    # Get the reviewer with the least pending reviews
    reviewer = active_reviewers.first()

    # Assign the task to the reviewer
    task.assigned_to = reviewer
    task.processing_status = "REVIEW_NEEDED"
    task.save()

    # Notify the reviewer about the new task
    dispatch_task_message(reviewer.id, serialize_task(task), action='task_created')

    return True


@shared_task
def assign_reviewers_to_cluster(cluster_id):
    """
    Assign reviewers to a cluster
    """
    
    try:
        cluster = TaskCluster.objects.get(id=cluster_id)
    except TaskCluster.DoesNotExist:
        return False
    
    domain = cluster.labeler_domain
    
    #get reviewers in this domain and order them by the ones that have the least assigned clusters (i.e the less busy ones)
    matching_reviewers = list(CustomUser.objects.filter(domains=domain, is_reviewer=True).annotate(assigned_count=Count('assigned_clusters', filter=~Q(assigned_clusters__status=TaskClusterStatusChoices.COMPLETED))).order_by('assigned_count'))    
    cluster.assigned_reviewers.add(*matching_reviewers[:cluster.labeller_per_item_count]) #since matching_reviewers is already ordered by the least busy ones, we can just add the first cluster.labeller_per_item_count ones
    cluster.save()
    return True

def calculate_labelling_required_data_points(cluster_data: dict) -> int:
    """
    Calculate the total data points required for a cluster item.

    Uses system settings for base cost, input type, task type, and per-labeller cost.
    Caches settings via `get_dp_cost_settings()` to avoid repeated DB queries.

    Returns:
        int: Total data points required for labeling this item.
    """
    settings = get_dp_cost_settings()
    datapoint = settings.get("base_cost", 10)

    input_type = cluster_data.get("input_type")
    if input_type:
        datapoint += settings.get(f"{input_type}_cost", 0)

    task_type = cluster_data.get("task_type")
    if task_type:
        datapoint += settings.get(f"task_{str(task_type).lower()}_cost", 0)

    labeller_count = cluster_data.get("labeller_per_item_count", 0)
    datapoint += labeller_count * settings.get("dp_cost_per_labeller", 10)

    return datapoint


def calculate_required_data_points(task_type, text_data=None, file_size_bytes=None)->int:
    """
    Calculate the number of data points required to process a task based on its type and content.
    
    This function determines the cost (in data points) for processing different types of tasks.
    Data points are consumed based on the complexity and resource requirements of each task type.
    
    Args:
        task_type (str): The type of task (TEXT, AUDIO, IMAGE, VIDEO, etc.)
        text_data (str, optional): The text content for text-based tasks
        file_size_bytes (int, optional): File size in bytes for file-based tasks
    
    Returns:
        int: Number of data points required to process the task
        
    """
    
    if task_type == 'TEXT' and text_data:
        text_length = len(text_data)
        if text_length <= 100:
            return 4
        elif text_length >100 and text_length <= 500:
            return 10
        else:
            return round(0.035 * text_length)
    
    if file_size_bytes and task_type in [TaskTypeChoices.AUDIO, TaskTypeChoices.IMAGE, TaskTypeChoices.VIDEO]:
        # Convert bytes to megabytes for easier calculation
        size_in_mb = file_size_bytes / (1024 * 1024)
        
        if task_type == TaskTypeChoices.AUDIO:
            # Audio: 10 points per MB, minimum 10 points
            return max(10, round(10 * size_in_mb))
            
        elif task_type == TaskTypeChoices.IMAGE:
            # Image: 5 points per MB, minimum 10 points
            return max(10, round(5 * size_in_mb))
            
        elif task_type == TaskTypeChoices.VIDEO:
            # Video: 15 points per MB, minimum 10 points
            return max(10, round(15 * size_in_mb))        
    return 20



def calculate_labeller_monthly_earning(labeler: CustomUser, year: int, month: int):
    """
    Calculate a labeller's earning for a given month using the formula:
    labeller_earnings = dpt × n × CR × P
    
    Where:
    - dpt = data points per task
    - n = cumulative number of tasks for that month
    - CR = Conversion rate from data points
    - P = labeller payout percentage
    """
    settings = get_dp_cost_settings()
    
    # Get all tasks labeled by this labeller in the specified month
    # Use timezone-aware datetimes
    if timezone.is_aware(timezone.now()):
        # If using timezone-aware datetime
        start_date = timezone.make_aware(datetime(year, month, 1))
        if month == 12:
            end_date = timezone.make_aware(datetime(year + 1, 1, 1))
        else:
            end_date = timezone.make_aware(datetime(year, month + 1, 1))
    else:
        # If using naive datetime
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
    
    # Get TaskLabels created by this labeller in the specified month
    from task.models import TaskLabel
    monthly_task_labels = TaskLabel.objects.filter(
        labeller=labeler,
        created_at__gte=start_date,
        created_at__lt=end_date
    ).select_related('task', 'task__cluster')
    
    # Get unique tasks labeled (since a task can have multiple labels from same user)
    labeled_task_ids = monthly_task_labels.values_list('task_id', flat=True).distinct()
    
    # Calculate total data points and task count
    total_data_points = 0
    task_count = len(labeled_task_ids)
    
    # Get the actual tasks to calculate data points
    from task.models import Task
    labeled_tasks = Task.objects.filter(id__in=labeled_task_ids).select_related('cluster')
    
    for task in labeled_tasks:
        task_dp = int(settings.get(f"task_{str(task.cluster.input_type).lower()}_cost", 0)) if task.task_type else 0
        total_data_points += task_dp
    
    # Get conversion rate and payout percentage
    cr_dollars = Decimal(settings.get("usd_per_dp_cents", 10)) / Decimal(100)  # Convert cents to dollars
    payout_percent = Decimal(settings.get("labeller_payout_percent", 60)) / Decimal(100)  # Convert to decimal
    
    # Calculate using the formula: dpt × n × CR × P
    # Note: This is equivalent to total_data_points × CR × P
    total_company_revenue = total_data_points * cr_dollars
    labeller_earning = total_company_revenue * payout_percent
    return labeller_earning


def credit_labeller_monthly_payment(labeler: CustomUser, year: int, month: int):
    """
    Calculate and credit a labeller's monthly earning to their balance.
    This should typically be called once per month per labeller.
    """
    payment_summary = calculate_labeller_monthly_earning(labeler, year, month)
    labeller_earning = payment_summary["labeller_earning_decimal"]
    
    if labeller_earning <= 0:
        return {
            "message": "No earnings to credit for this month",
            "credited_usd": "$0.00",
            **payment_summary
        }
    
    # Credit the labeller's balance
    earnings, _ = LabelerEarnings.objects.get_or_create(labeler=labeler)
    earnings.balance = models.F('balance') + labeller_earning
    earnings.save(update_fields=['balance'])
    earnings.refresh_from_db(fields=['balance'])
    
    # Optional: Create a payment record for audit trail
    # TODO : Have a separate model for monthly payment
    try:
        MonthlyPayment.objects.create(
            labeler=labeler,
            year=year,
            month=month,
            amount=labeller_earning,
            created_at=timezone.now()
        )
    except:
        pass  # Handle if MonthlyPayment model doesn't exist
    
    return {
        "message": "Monthly payment credited successfully",
        "credited_usd": f"${labeller_earning:.2f}",
        "new_balance": f"${earnings.balance:.2f}",
        **payment_summary,
    }

def track_task_labeling_earning(task, labeler: CustomUser):
    """
    Called when a labeler completes labeling a task.
    This tracks their contribution for monthly payment calculation.
    Returns information about the earning contribution without actually crediting balance.
    """
    settings = get_dp_cost_settings()
    task_dp = int(settings.get(f"task_{str(task.cluster.task_type).lower()}_cost", 0)) if task.task_type else 0
    
    if task_dp <= 0:
        return {
            "message": "No data points assigned to this task type",
            "task_dp": 0,
            "task_earning_preview": "$0.00",
            "labeler_id": labeler.id,
            "task_id": task.id,
            "task_serial": getattr(task, 'serial_no', 'N/A')
        }
    
    # Calculate what this task contributes to their monthly earnings
    cr_dollars = Decimal(settings.get("usd_per_dp_cents", 10)) / Decimal(100)
    payout_percent = Decimal(settings.get("labeller_payout_percent", 60)) / Decimal(100)
    
    task_revenue = task_dp * cr_dollars
    task_earning = task_revenue * payout_percent
    
    return task_earning

def get_labeller_current_month_preview(labeler: CustomUser):
    """
    Get a preview of the current month's earnings for a labeller
    """
    now = timezone.now()
    monthly_summary = {}
    monthly_summary['amount'] = calculate_labeller_monthly_earning(labeler, now.year, now.month)
    
    # Add some additional helpful information
    monthly_summary["current_month"] = now.strftime("%B %Y")
    
    # Calculate days left in month using timezone-aware datetime
    if now.month == 12:
        next_month_start = timezone.make_aware(datetime(now.year + 1, 1, 1)) if timezone.is_aware(now) else datetime(now.year + 1, 1, 1)
    else:
        next_month_start = timezone.make_aware(datetime(now.year, now.month + 1, 1)) if timezone.is_aware(now) else datetime(now.year, now.month + 1, 1)
    
    monthly_summary["days_left_in_month"] = (next_month_start - now).days
    
    return monthly_summary
 
def get_labeller_monthly_history(labeler: CustomUser, months_back: int = 6):
    """
    Get earning history for the last N months for a labeller
    """
    now = timezone.now()
    history = []
    
    for i in range(months_back):
        # Calculate month and year going backwards
        target_month = now.month - i
        target_year = now.year
        
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        monthly_earnings = {}
        monthly_earnings['amount'] = calculate_labeller_monthly_earning(labeler, target_year, target_month)
        monthly_earnings["month_year"] = datetime(target_year, target_month, 1).strftime("%B %Y")
        history.append(monthly_earnings)
    
    return {
        "labeller_username": labeler.username,
        "months_included": months_back,
        "history": history,
    }
