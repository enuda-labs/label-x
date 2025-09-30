from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts  import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
import logging
from datetime import datetime
from rest_framework.views import APIView
from rest_framework_api_key.permissions import HasAPIKey
from account.choices import ProjectStatusChoices
from account.models import Project, CustomUser, LabelerEarnings
from common.caching import cache_response_decorator
from common.responses import ErrorResponse, SuccessResponse, format_first_error
from subscription.models import UserDataPoints
from task.choices import AnnotationMethodChoices, ManualReviewSessionStatusChoices, TaskClusterStatusChoices, TaskInputTypeChoices, TaskTypeChoices
from task.utils import assign_reviewers_to_cluster, calculate_labelling_required_data_points, calculate_required_data_points, dispatch_task_message, push_realtime_update
from .models import ManualReviewSession, MultiChoiceOption, Task, TaskCluster, UserReviewChatHistory, TaskLabel
from .serializers import AcceptClusterIdSerializer, AssignedTaskSerializer, FullTaskSerializer, GetAndValidateReviewersSerializer, ListReviewersWithClustersSerializer, MultiChoiceOptionSerializer, RequestAdditionalLabellersSerializer, TaskAnnotationSerializer, TaskClusterCreateSerializer, TaskClusterDetailSerializer, TaskClusterListSerializer, TaskIdSerializer, TaskSerializer, TaskReviewSerializer, AssignTaskSerializer
from .tasks import process_task, provide_feedback_to_ai_model

# import custom permissions
from account.utils import HasUserAPIKey, IsAdminUser, IsReviewer
from django.db.models import Q, Count, Avg, F, Sum
import csv

# from task.choices import TaskClassificationChoices


logger = logging.getLogger('task.apis')

class ExportClusterToCsvView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated | HasAPIKey]
    
    @extend_schema(
        summary="Export a cluster to CSV",
        description="Export a cluster to CSV",
        responses={
            200: OpenApiResponse(response=None, description="Cluster exported to CSV"),
            404: OpenApiResponse(response=None, description="Cluster not found"),
        }
    )
    def get(self, request, *args, **kwargs):
        cluster_id = kwargs.get('cluster_id')
        
        try:
            cluster = TaskCluster.objects.get(id=cluster_id)
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        
        if cluster.created_by != request.user:
            return ErrorResponse(message="You are not authorized to export this data", status=status.HTTP_403_FORBIDDEN)
        
        labels = TaskLabel.objects.filter(task__cluster=cluster)
        
        response = HttpResponse(content_type='text/csv')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{cluster.project.name}_{cluster.id}_{timestamp}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        headers = ['Task ID', 'Task Data', 'Label', 'notes', 'Labeller', 'Created At', 'Updated At']
        writer.writerow(headers)
        
        is_text_input_type = cluster.input_type  in [TaskInputTypeChoices.TEXT, TaskInputTypeChoices.MULTIPLE_CHOICE]
        
        for label in labels:
            task_data = label.task.data if label.task.task_type == TaskTypeChoices.TEXT else label.task.file_url
            task_label = label.label if is_text_input_type else label.label_file_url
            
            row = [label.task.id, task_data, task_label, label.notes, label.labeller.username, label.created_at, label.updated_at]
            writer.writerow(row)
        
        return response
        




class RemoveReviewersFromCluster(generics.GenericAPIView):
    
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = GetAndValidateReviewersSerializer
    
    @extend_schema(
        summary="Remove reviewers from a cluster",
        description="Remove reviewers from a cluster",
        request=GetAndValidateReviewersSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Reviewers removed from cluster",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value=[
                            {
                                "id": 1,
                                "username": "user1",
                                "email": "user1@example.com",
                                "is_active": True
                            },
                            {
                                "id": 2,
                                "username": "user2",
                                "email": "user2@example.com",
                                "is_active": True
                            }
                        ],
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, False))
                
        try:
            cluster = TaskCluster.objects.get(id=kwargs.get('cluster_id'))
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        
        
        reviewer_ids = request.data.get('reviewer_ids')
        for reviewer_id in reviewer_ids:
            reviewer = CustomUser.objects.get(id=reviewer_id)
            cluster.assigned_reviewers.remove(reviewer)
            
        return SuccessResponse(message="Reviewers removed from cluster", data=cluster.assigned_reviewers.values('id', 'username', 'email', 'is_active'))

class AssignReviewersToCluster(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = GetAndValidateReviewersSerializer
    @extend_schema(
        summary="Assign reviewers to a cluster",
        description="Assign reviewers to a cluster",
        request=GetAndValidateReviewersSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Reviewers assigned to cluster",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value=[
                            {
                                "id": 1,
                                "username": "user1",
                                "email": "user1@example.com",
                                "is_active": True
                            },
                            {
                                "id": 2,
                                "username": "user2",
                                "email": "user2@example.com",
                                "is_active": True
                            }
                        ],
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, False))
        
        cluster_id = kwargs.get('cluster_id')
        try:
            cluster = TaskCluster.objects.get(id=cluster_id)
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        
        reviewer_ids = serializer.validated_data.get('reviewer_ids')
        if cluster.assigned_reviewers.count() + len(reviewer_ids) > cluster.labeller_per_item_count:
            return ErrorResponse(message="This cluster has reached its maximum number of assigned reviewers")
        
        for reviewer_id in reviewer_ids:
            #user is already validated in the serializer
            reviewer = CustomUser.objects.get(id=reviewer_id)
            cluster.assigned_reviewers.add(reviewer)
            
        if cluster.status == TaskClusterStatusChoices.COMPLETED:
            #if the cluster was previously completed and another reviewer is assigned to it, set the status to in review
            cluster.status = TaskClusterStatusChoices.IN_REVIEW
            cluster.save()
            
        return SuccessResponse(message="Reviewers assigned to cluster", data=cluster.assigned_reviewers.values('id', 'username', 'email', 'is_active'))


class GetClusterReviewers(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary="Get the reviewers assigned to a cluster",
        description="Get the reviewers assigned to a cluster",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Cluster reviewers",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value=[
                            {
                                "id": 1,
                                "username": "user1",
                                "email": "user1@example.com",
                                "is_active": True
                            },
                            {
                                "id": 2,
                                "username": "user2",
                                "email": "user2@example.com",
                                "is_active": True
                            }
                        ],
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request, *args, **kwargs):
        try:
            cluster_id = kwargs.get('cluster_id')
            cluster = TaskCluster.objects.get(id=cluster_id)
            return SuccessResponse(message="Cluster reviewers", data=ListReviewersWithClustersSerializer(cluster.assigned_reviewers, many=True).data)
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
    

class RequestAdditionalLabellersView(generics.GenericAPIView):
    """
    API endpoint to allow clients to request additional labellers for their cluster.
    Charges DPT based on system settings.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = RequestAdditionalLabellersSerializer
    
    @extend_schema(
        summary="Request additional labellers for a cluster",
        description="Request additional labellers to be added to a cluster. Charges DPT based on system settings.",
        request=RequestAdditionalLabellersSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Additional labellers requested successfully",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "message": "Additional labellers requested successfully",
                            "data": {
                                "cluster_id": 1,
                                "requested_labellers": 10,
                                "dpt_charged": 10,
                                "remaining_dpt_balance": 450
                            }
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(description="Invalid request data"),
            402: OpenApiResponse(description="Insufficient DPT balance"),
            404: OpenApiResponse(description="Cluster not found"),
            403: OpenApiResponse(description="Permission denied")
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, False))
        
        cluster_id = serializer.validated_data['cluster_id']
        additional_labellers_count = serializer.validated_data['additional_labellers_count']
        
        try:
            # Get the cluster
            cluster = TaskCluster.objects.get(id=cluster_id)
            
            # Get system settings for DPT cost per labeller
            from common.utils import get_dp_cost_settings
            settings = get_dp_cost_settings()
            dpt_cost_per_labeller = settings.get('dp_cost_per_labeller', 10)
            
            
            # Check user's DPT balance
            user_data_points, created = UserDataPoints.objects.get_or_create(user=request.user)
            
            if user_data_points.data_points_balance < dpt_cost_per_labeller:
                return ErrorResponse(
                    message=f"Insufficient DPT balance. Required: {dpt_cost_per_labeller}, Available: {user_data_points.data_points_balance}",
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )
            
            # Deduct DPT from user's balance and refresh to avoid returning CombinedExpression
            user_data_points.deduct_data_points(dpt_cost_per_labeller)
            user_data_points.refresh_from_db()
            
            # Update cluster's labeller_per_item_count
            cluster.labeller_per_item_count += additional_labellers_count
            cluster.save()
            
            # Trigger automatic assignment of new labellers
            assign_reviewers_to_cluster.delay(cluster.id)
            
            logger.info(f"User '{request.user.username}' requested {additional_labellers_count} additional labellers for cluster {cluster_id} at {datetime.now()}")
            
            return SuccessResponse(
                message="Additional labellers requested successfully",
                data={
                    "cluster_id": cluster_id,
                    "requested_labellers": additional_labellers_count,
                    "dpt_charged": dpt_cost_per_labeller,
                    "remaining_dpt_balance": int(user_data_points.data_points_balance)
                }
            )
            
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error requesting additional labellers: {str(e)}")
            return ErrorResponse(message="An error occurred while processing your request", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetProjectClusters(generics.ListAPIView):
    serializer_class = TaskClusterListSerializer
    def get_queryset(self):
        return TaskCluster.objects.filter(project=self.kwargs.get('project_id'))
    
    def get(self, request, *args, **kwargs):
        try:
            Project.objects.get(id=kwargs.get('project_id'))
        except Project.DoesNotExist:
            return ErrorResponse(message="Project not found")
        return super().get(request, *args, **kwargs)

class GetPendingClusters(generics.GenericAPIView):
    
    @extend_schema(
        summary="Get pending clusters",
        description="Retrieve the list of clusters that this user is currently reviewing, but where they have not yet completed labeling all tasks within the cluster."
    )
    def get(self, request):
        review_session_clusters = ManualReviewSession.objects.filter(labeller=request.user, status=ManualReviewSessionStatusChoices.STARTED).values_list('cluster_id', flat=True)
        clusters = TaskCluster.objects.filter(id__in=review_session_clusters)
        return SuccessResponse(message="Pending clusters", data=TaskClusterListSerializer(clusters, many=True).data)

class UserClusterAnnotatedTasksView(generics.GenericAPIView):
    
    @extend_schema(
        summary="Get the tasks the currently logged in user has annotated in a particular cluster"
    )
    def get(self, request, *args, **kwargs):
        cluster_id = kwargs.get('cluster_id')
        
        try:
            cluster = TaskCluster.objects.get(id=cluster_id)
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        
        user_labelled_tasks_ids = TaskLabel.objects.filter(task__cluster=cluster, labeller=request.user).values_list('task__id', flat=True)
        user_labelled_tasks = Task.objects.filter(id__in=user_labelled_tasks_ids)
        
        
        return SuccessResponse(message="", data=TaskSerializer(user_labelled_tasks, many=True).data)

class TaskListView(generics.ListAPIView):
    """
    Get a list of tasks the currently logged in user can work on
    
    ---
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    queryset = Task.objects.all()
    
    def get_queryset(self):
        # Get tasks from clusters where the current user is assigned as a reviewer
        tasks_list = Task.objects.filter(
            cluster__assigned_reviewers=self.request.user,
            assigned_to=None,
            processing_status="REVIEW_NEEDED"
        ).select_related('cluster', 'group')
        
        logger.info(f"User '{self.request.user.username}' fetched {tasks_list.count()} available tasks at {datetime.now()}")
        return tasks_list

class GetClusterDetailView(generics.RetrieveAPIView):
    serializer_class = TaskClusterDetailSerializer
    lookup_field = 'id'
    queryset = TaskCluster.objects.all()
    permission_classes = [IsAuthenticated]   
    
    @extend_schema(
        summary="Get the full details of a task cluster by id"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class CreatedClusterListView(generics.ListAPIView):
    serializer_class = TaskClusterListSerializer
    def get_queryset(self):
        return TaskCluster.objects.filter(created_by=self.request.user)
    
    @extend_schema(
        summary="Get all clusters that were created by the currently logged in user"
    )
    
    @cache_response_decorator('created_clusters', per_user=True)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class GetAvailableClusters(generics.ListAPIView):
    serializer_class = TaskClusterListSerializer
    def get_queryset(self):
        user_domains = self.request.user.domains.all()
 
        return TaskCluster.objects.annotate(reviewer_count=Count("assigned_reviewers")).filter(
            ~Q(status=TaskClusterStatusChoices.COMPLETED) & 
            ~Q(annotation_method=AnnotationMethodChoices.AI_AUTOMATED) &
            Q(reviewer_count__lt=F("labeller_per_item_count"))
            & Q(labeler_domain__in=user_domains)
        ).exclude(assigned_reviewers=self.request.user)
    
    @extend_schema(
        summary="Get all the clusters that are available for assignment",
        description="Ideal for when a reviewer is looking for clusters to assign to themselves"
    )
    @cache_response_decorator('available_clusters', per_user=True)
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class TaskClusterCreateView(generics.GenericAPIView):
    serializer_class = TaskClusterCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, False))
        
        # get the tasks before saving the cluster because they get popped out in the create method of the serializer
        tasks = serializer.validated_data.get('tasks')
        # required_data_points = serializer.validated_data.get('required_data_points')
        labelling_choices = serializer.validated_data.get('labelling_choices', [])
        
        user_data_point, created = UserDataPoints.objects.get_or_create(user=request.user)
    
        required_data_points = calculate_labelling_required_data_points(serializer.validated_data)
                
        if user_data_point.data_points_balance < required_data_points:
            return ErrorResponse(message="You do not have enough data points to satisfy this request")

        cluster = serializer.save(created_by=request.user)
        # cluster= serializer.save(created_by=request.user)
        task_type = serializer.validated_data.get('task_type')
        annotation_method = serializer.validated_data.get('annotation_method')
        
        for task in tasks:
            if task_type == 'TEXT':
                extra_kwargs = {
                    "data": task.get('data')
                }
            else:
                file = task.get('file')
                extra_kwargs = {
                    "file_name": file.get('file_name'),
                    "file_type": file.get('file_type'),
                    "file_url": file.get('file_url'),
                    "file_size_bytes": file.get('file_size_bytes')
                }
            
            Task.objects.create(
                cluster = cluster,
                user=request.user,
                group = cluster.project, #TODO: REMOVE THIS LATER,
                task_type=cluster.task_type,
                processing_status= 'REVIEW_NEEDED' if annotation_method == "manual" else "PENDING", #review_needed indicates that a human needs to review this task
                used_data_points=task.get('required_data_points', 0),
                **extra_kwargs
            )
        
        if cluster.input_type == TaskInputTypeChoices.MULTIPLE_CHOICE:
            for choice in labelling_choices:
                MultiChoiceOption.objects.create(cluster=cluster, option_text=choice.get('option_text'))
        
        user_data_point.deduct_data_points(required_data_points)
        
        if annotation_method == AnnotationMethodChoices.AI_AUTOMATED:
            tasks = Task.objects.select_related("cluster").filter(cluster=cluster)
            for task in tasks:
                process_task.delay(task.id)
        
            return SuccessResponse(message="Cluster created successfully, tasks have been queued for AI annotation", data=TaskClusterDetailSerializer(cluster).data)
        
        # assign_reviewers_to_cluster.delay(cluster.id)
        return SuccessResponse(message="Cluster created successfully", data=TaskClusterDetailSerializer(cluster).data)
        
    
    
class TaskCreateView(generics.CreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    
    def get_queryset(self):
        return Task.objects.select_related('group').all()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            task_type = serializer.validated_data.get("task_type")
            required_dp = calculate_required_data_points(task_type, text_data=serializer.validated_data.get("data"))
            if not required_dp:
                return Response({
                    "status": "error",
                    "data": {
                        "message": "Error calculating required data points"
                    }
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            user_data_points, created = UserDataPoints.objects.get_or_create(user=request.user)
            if user_data_points.data_points_balance < required_dp:
                return Response({
                    "status": "error",
                    "data": {
                        "message": "You do not have enough data points left to satisfy this request"
                    }
                }, status=status.HTTP_402_PAYMENT_REQUIRED)

            
            try:
                task_cluster = TaskCluster.objects.create(project=serializer.validated_data.get('group')) #create a cluster which will contain this single task
                
                task = serializer.save(user=request.user, used_data_points=required_dp, cluster=task_cluster)
                logger.info(f"User '{request.user.username}' created new task {task.id} (Serial: {task.serial_no}) at {datetime.now()}")
                
                celery_task = process_task.delay(task.id)
                logger.info(f"Task {task.id} submitted to Celery queue. Celery task ID: {celery_task.id} at {datetime.now()}")

                task = Task.objects.select_related('group').get(id=task.id)
                
                user_data_points.deduct_data_points(required_dp)
                
                task.create_log(f"Queued task {str(task.id)}, serial no: {task.serial_no}")
                return Response({
                    'status': 'success',
                    'data': {
                        'message': 'Task submitted successfully',
                        'task_id': task.id,
                        'serial_no': task.serial_no,
                        'celery_task_id': celery_task.id,
                        'processing_status': task.processing_status,
                    }
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Task creation failed for user '{request.user.username}': {str(e)}", exc_info=True)
                return Response({
                    'status': 'error',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.error(f"Task creation validation failed for user '{request.user.username}': {serializer.errors}")
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
class TasksNeedingReviewView(APIView):
    """
    View all tasks that need review (Admins or Reviewers)
    """
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="View all tasks that need review",
        description="Admins and Reviewers can view tasks that are awaiting review. "
                    "This includes filtering by the user's associated project and tasks with the "
                    "'REVIEW_NEEDED' processing status.",
        request=None,  # No request body
        responses={
            200: TaskSerializer(many=True),
            403: OpenApiExample(
                "Unauthorized",
                value={"detail": "Not authorized."},
                response_only=True
            ),
        },
        examples=[
            OpenApiExample(
                "Tasks Needing Review Example",
                value=[
                    {
                        "id": 1,
                        "serial_no": "T12345",
                        "task_type": "text_classification",
                        "data": {"text": "This is an example task data."},
                        "ai_output": {
                            "label": "positive",
                            "confidence": 0.95
                        },
                        "predicted_label": "positive",
                        "human_reviewed": False,
                        "final_label": None,
                        "processing_status": "REVIEW_NEEDED",
                        "assigned_to": None,
                        "created_at": "2025-04-15T07:58:59Z",
                        "updated_at": "2025-04-15T08:00:00Z",
                        "priority": "NORMAL",
                        "group": 1  # Reference to a project/group ID
                    }
                ],
                response_only=True
            ),
        ]
    )
    
    def get(self, request):
        if not (request.user.is_admin or request.user.is_reviewer):
            logger.warning(f"Unauthorized access attempt to review tasks by user '{request.user.username}' at {datetime.now()}")
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        
        # Get tasks where user is assigned to review the cluster and task needs review
        tasks = Task.objects.filter(
            processing_status='REVIEW_NEEDED',
            cluster__assigned_reviewers=request.user,
            assigned_to=None
        ).select_related('cluster', 'group')
        
        logger.info(f"Reviewer '{request.user.username}' fetched {tasks.count()} tasks needing review at {datetime.now()}")
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

class AssignClusterToSelf(generics.GenericAPIView):
    serializer_class = AcceptClusterIdSerializer
    permission_classes = [IsAuthenticated, IsReviewer]
    
    @extend_schema(
        summary="Add currently logged in use to assigned reviewers for a cluster"
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors))

        cluster = serializer.validated_data.get("cluster")
        
        if cluster.assigned_reviewers.count() >= cluster.labeller_per_item_count:
            return ErrorResponse(message="This cluster has reached its maximum number of assigned reviewers")

        if not cluster.assigned_reviewers.filter(id=request.user.id).exists():
            cluster.assigned_reviewers.add(request.user)
            
            if cluster.status == TaskClusterStatusChoices.COMPLETED: 
                #if the cluster was previously completed and another reviewer is assigned to it, set the status to in review
                cluster.status = TaskClusterStatusChoices.IN_REVIEW
                cluster.save()
                
        else:
            return ErrorResponse(message="You are already assigned to this cluster")

        cache.delete_pattern(f"*available_clusters_{request.user.id}*")
        return SuccessResponse(message="Successfully added user to assigned reviewers")

class AssignTaskToSelfView(APIView):
    """
    Allow a reviewer to assign a REVIEW_NEEDED task to themselves.
    Expects POST payload: { "task_id": 123 }
    """
    permission_classes = [IsReviewer]
    serializer_class= AssignTaskSerializer
    
    @extend_schema(
        summary="Assign a task to self",
        description="Allows a reviewer to claim a task for review if it is in REVIEW_NEEDED state and unassigned.",
        request=AssignTaskSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Task successfully assigned",
                examples=[
                    OpenApiExample(
                        "Successful Assignment",
                        value={
                            "status": "success",
                            "message": "Task T12345 assigned to you."
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                response=None,
                description="Invalid task or already assigned",
                examples=[
                    OpenApiExample(
                        "Task Already Assigned",
                        value={
                            "status": "error",
                            "detail": "Task is already assigned."
                        },
                        response_only=True
                    ),
                    OpenApiExample(
                        "Invalid Status",
                        value={
                            "status": "error",
                            "detail": "Task is not available for review."
                        },
                        response_only=True
                    ),
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Assign Task Request",
                value={"task_id": 123},
                request_only=True
            )
        ]
    )

    def post(self, request):
        serializer = AssignTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = serializer.validated_data['task_id']
        task = get_object_or_404(Task, id=task_id)

        if task.processing_status != 'REVIEW_NEEDED':
            logger.warning(f"Reviewer '{request.user.username}' attempted to assign task {task_id} with invalid status '{task.processing_status}' at {datetime.now()}")
            return Response(
                {"status": "error", "detail": "Task is not available for review."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if user is assigned to review this cluster
        if not task.cluster or request.user not in task.cluster.assigned_reviewers.all():
            logger.warning(f"Unauthorized reviewer '{request.user.username}' attempted to assign task {task_id} at {datetime.now()}")
            return Response(
                {"status": "error", "detail": "You are not assigned to review this task cluster."},
                status=status.HTTP_403_FORBIDDEN
            )

        if task.assigned_to:
            logger.warning(f"Reviewer '{request.user.username}' attempted to assign already assigned task {task_id} at {datetime.now()}")
            return Response(
                {"status": "error", "detail": "Task is already assigned."},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.assigned_to = request.user
        task.processing_status = 'ASSIGNED_REVIEWER'
        task.review_status = "PENDING_REVIEW"
        task.save()
        push_realtime_update(task, action='task_status_changed')

        logger.info(f"Reviewer '{request.user.username}' successfully assigned task {task.serial_no} to self at {datetime.now()}")
        return Response(
            {"status": "success", "message": f"Task {task.serial_no} assigned to you."},
            status=status.HTTP_200_OK
        )

class MyPendingReviewTasks(APIView):
    permission_classes = [IsReviewer]
    
    @extend_schema(
        summary="List My Pending Review Tasks",
        description="Returns all tasks assigned to the authenticated reviewer that are in `PENDING_REVIEW` status.",
        responses={
            200: OpenApiResponse(
                response=TaskSerializer(many=True),
                description="List of pending review tasks assigned to the user",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value=[
                            {
                                "id": 12,
                                "serial_no": "T12345",
                                "task_type": "classification",
                                "data": {"text": "Example input text"},
                                "ai_output": {"prediction": "label_1"},
                                "predicted_label": "label_1",
                                "human_reviewed": False,
                                "final_label": None,
                                "processing_status": "ASSIGNED_REVIEWER",
                                "assigned_to": 7,
                                "created_at": "2024-04-01T10:00:00Z",
                                "updated_at": "2024-04-02T10:00:00Z",
                                "priority": "NORMAL",
                                "group": 3
                            }
                        ],
                        response_only=True
                    )
                ]
            )
        }
    )

    def get(self, request):
        # Get tasks assigned to the current user for review
        tasks = Task.objects.select_related('assigned_to', 'group', 'cluster').filter(
            assigned_to=request.user,
            review_status='PENDING_REVIEW'
        )
       
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

class CompleteTaskReviewView(generics.GenericAPIView):
    """
    After using the websocket to review a task, use this endpoint to save the final decision
    
    ---
    """
    serializer_class = TaskIdSerializer
    permission_classes =[IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(data=serializer.errors, message="Error validating request")
        
        task_id = serializer.validated_data.get('task_id')
        
        try:
            task = Task.objects.get(id=task_id)
            last_human_review = UserReviewChatHistory.objects.filter(task=task).order_by('-created_at').first()
            
            if not last_human_review:
                return ErrorResponse(message="This task has not been reviewed by a human")
            
            task.processing_status = 'COMPLETED'
            task.review_status = 'PENDING_APPROVAL'
            task.human_reviewed = True
            task.final_label = last_human_review.ai_output.get('corrected_classification')
            task.save()
            
            push_realtime_update(task, action='task_status_changed')
            
            return SuccessResponse(message="Task review complete", data=TaskSerializer(task).data)
        except Task.DoesNotExist:
            return ErrorResponse(message="Task not found")

class TaskReviewView(generics.GenericAPIView):
    """View for submission of review by a reviewer"""
    serializer_class = TaskReviewSerializer
    permission_classes = [IsAuthenticated, IsReviewer]
    @extend_schema(
        summary="Submit task review",
        description="Submit a review for an existing task with AI output data.",
        request=TaskReviewSerializer,
        responses={
            200: TaskReviewSerializer,
            400: None,
            404: None,
            500: None
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid review submission by '{request.user.username}': {serializer.errors}")
            return Response({
                'status': 'error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)  
            
        task_id = serializer.validated_data.get('task_id')            
        try:
            task = Task.objects.select_related('user', 'assigned_to').get(id=task_id)

            if task.review_status != 'PENDING_REVIEW':
                logger.warning(f"Reviewer '{request.user.username}' attempted to review task {task_id} with invalid status '{task.review_status}' at {datetime.now()}")
                return Response({
                    'status': "error",
                    'error': "Task does not require review at this moment"
                }, status=status.HTTP_403_FORBIDDEN)

            if task.assigned_to != request.user and not request.user.is_admin:
                logger.warning(f"Unauthorized review attempt by '{request.user.username}' for task {task_id} at {datetime.now()}")
                return Response({
                    'status': "error",
                    'error': "You have not been assigned to review this task"
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            ai_output = task.ai_output
            if not ai_output or not ai_output.get('human_review'):
                logger.error(f"Invalid AI output structure for task {task_id} reviewed by '{request.user.username}' at {datetime.now()}")
                return Response({
                    'status': 'error',
                    'error': "AI output for this task does not match predefined structure"
                }, status=status.HTTP_417_EXPECTATION_FAILED)
            
            ai_output['human_review']['correction'] = serializer.validated_data.get('correction')
            ai_output['human_review']['justification'] = serializer.validated_data.get('justification')
            ai_output['confidence'] = serializer.validated_data.get('confidence')
            
            logger.info(f"Reviewer '{request.user.username}' submitted review for task {task.serial_no} at {datetime.now()}")
            
            celery_task = provide_feedback_to_ai_model.delay(task.id, ai_output)
            logger.info(f"Task {task.id} review submitted to Celery. Celery task ID: {celery_task.id} at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'message': 'Task queued for review',
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'celery_task_id': celery_task.id,
                    'processing_status': task.processing_status,
                }
            }, status=status.HTTP_200_OK)
            
        except Task.DoesNotExist:
            logger.error(f"Task {task_id} not found for review by '{request.user.username}' at {datetime.now()}")
            return Response({
                'status': 'error',
                'error': f"Task with ID {task_id} not found."
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Failed to queue task review: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class TaskStatusView(APIView):
    """
    Endpoint to check the status of a task by ID or serial number
    """
    def get(self, request, identifier):
        logger.info(f"User '{request.user.username}' checking status for task identifier: {identifier} at {datetime.now()}")
        
        try:
            tasks_qs = Task.objects.select_related('user', 'assigned_to', 'group', 'cluster')
            
            if identifier.isdigit():
                task = tasks_qs.get(id=identifier, user=request.user)
            else:
                task = tasks_qs.get(serial_no=identifier, user=request.user)
            
            logger.info(f"Task {task.id} status retrieved for user '{request.user.username}' at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'task_type': task.task_type,
                    'processing_status': task.processing_status,
                    'human_reviewed': task.human_reviewed,
                    "ai_output": task.ai_output,
                    'submitted_by': task.user.username if task.user else None,
                    'assigned_to': task.assigned_to.username if task.assigned_to else None,
                    'cluster_id': task.cluster.id if task.cluster else None,
                    'cluster_reviewers': [user.username for user in task.cluster.assigned_reviewers.all()] if task.cluster else [],
                    'created_at': task.created_at,
                    'updated_at': task.updated_at
                }
            })
            
        except Task.DoesNotExist:
            logger.error(f"Task not found for identifier: {identifier} requested by '{request.user.username}' at {datetime.now()}")
            return Response({
                'status': 'error',
                'error': 'Task not found'
            }, status=status.HTTP_404_NOT_FOUND)

class UserTaskListView(generics.ListAPIView):
    """
    Endpoint to list all tasks submitted by the user
    """
    serializer_class = FullTaskSerializer
    
    def get_queryset(self):
        logger.info(f"User '{self.request.user.username}' fetching their task list at {datetime.now()}")
        return (Task.objects
                .select_related('user', 'assigned_to', 'group', 'cluster')
                .filter(user=self.request.user)
                .order_by('-created_at'))
        
        
class AssignedTaskListView(generics.ListAPIView):
    """
    Endpoint to list all tasks assigned to the authenticated user
    """
    serializer_class = AssignedTaskSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
    summary="List tasks assigned to the authenticated user",
    description="Retrieve a list of all tasks currently assigned to the authenticated user, ordered by creation date (descending).",
    responses={
        200: OpenApiResponse(
            response=TaskSerializer(many=True),
            description="List of tasks assigned to the user",
            examples=[
                OpenApiExample(
                    "Successful Response Example",
                    value=[
                        {
                            "id": 42,
                            "serial_no": "T98765",
                            "task_type": "classification",
                            "data": {"text": "Sample text input"},
                            "ai_output": {"prediction": "positive"},
                            "predicted_label": "positive",
                            "human_reviewed": False,
                            "final_label": None,
                            "processing_status": "ASSIGNED_REVIEWER",
                            "review_status": "PENDING_REVIEW",
                            "assigned_to": 10,
                            "created_at": "2024-03-20T12:00:00Z",
                            "updated_at": "2024-03-21T12:00:00Z",
                            "priority": "NORMAL",
                            "group": 2
                        }
                    ],
                    response_only=True
                )
            ]
        )
    }
)
    def get_queryset(self):
        logger.info(f"User '{self.request.user.username}' fetching their assigned tasks at {datetime.now()}")
        return (Task.objects
                .select_related('assigned_to', 'group', 'cluster')
                .filter(assigned_to=self.request.user)
                .order_by('-created_at'))

class TaskCompletionStatsView(generics.GenericAPIView):
    """
    View to get task completion statistics for tasks submitted by the logged-in user
    """
    permission_classes = [IsAuthenticated]
    cache_prefix = 'task_completion_stats'

    
    @extend_schema(
        summary="Get task completion statistics",
        description="Returns the percentage of completed tasks out of total tasks submitted by the logged-in user.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Task completion statistics",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "data": {
                                "total_tasks": 100,
                                "completed_tasks": 75,
                                "completion_percentage": 75.0
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
        
    @cache_response_decorator('task_completion_stats', per_user=True)
    def get(self, request):        
        try:
            user_clusters = TaskCluster.objects.filter(created_by=request.user)
            
            # user_tasks = Task.objects.filter(user=request.user)
            user_projects = Project.objects.filter(created_by=request.user)
            
            # Get total tasks count for the logged-in user
            total_tasks = user_clusters.count()
            
            completed_tasks = user_clusters.filter(status=TaskClusterStatusChoices.COMPLETED).count()
            
            # Get clusters where user is assigned as reviewer
            assigned_clusters = TaskCluster.objects.filter(assigned_reviewers=request.user).count()
            
            # Calculate percentage
            completion_percentage = user_clusters.aggregate(completion_percentage=Avg("completion_percentage"))["completion_percentage"]  or 0
            
            # completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
            logger.info(f"User '{request.user.username}' fetched their task completion stats at {datetime.now()}")
            
            return Response({
                "status": "success",
                "data": {
                    "total_tasks": total_tasks ,
                    "total_projects": user_projects.count(),
                    "completed_tasks": completed_tasks,
                    "completion_percentage": round(completion_percentage, 2),
                    "pending_projects": user_projects.filter(Q(status=ProjectStatusChoices.PENDING) | Q(status=ProjectStatusChoices.IN_PROGRESS)).count(),
                    "assigned_clusters": assigned_clusters
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error calculating task completion stats for user '{request.user.username}': {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": "Failed to calculate task completion statistics"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MyAssignedClustersView(APIView):
    """
    View to list all clusters assigned to the authenticated user for review
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List clusters assigned to the authenticated user",
        description="Retrieve a list of all task clusters currently assigned to the authenticated user for review.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="List of assigned clusters",
                examples=[
                    OpenApiExample(
                        "Successful Response Example",
                        value={
                            "status": "success",
                            "data": [
                                {
                                    "id": 1,
                                    "input_type": "text",
                                    "task_type": "TEXT",
                                    "annotation_method": "manual",
                                    "project": 4,
                                    "deadline": "2025-08-29",
                                    "labeller_per_item_count": 100,
                                    "labeller_instructions": "Review the text content",
                                    "tasks_count": 5
                                }
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    
    def get(self, request):
        try:
            # Get clusters assigned to the current user
            # assigned_clusters = TaskCluster.objects.filter(
            #     assigned_reviewers=request.user
            # ).select_related('project').prefetch_related('tasks')
            
            assigned_clusters = TaskCluster.objects.filter(assigned_reviewers=request.user).select_related('project').prefetch_related('tasks', "choices").annotate(
                tasks_count=Count("tasks"),
                user_labels_count=Count("tasks", filter=Q(tasks__tasklabel__labeller=request.user), distinct=True)
            )
            
            # Prepare response data
            clusters_data = []
            for cluster in assigned_clusters:
                clusters_data.append({
                    'id': cluster.id,
                    'input_type': cluster.input_type,
                    'task_type': cluster.task_type,
                    'annotation_method': cluster.annotation_method,
                    'project': cluster.project.id,
                    'project_name': cluster.project.name,
                    'deadline': cluster.deadline,
                    'labeller_per_item_count': cluster.labeller_per_item_count,
                    'labeller_instructions': cluster.labeller_instructions,
                    'tasks_count': cluster.tasks_count,
                    'pending_tasks': cluster.tasks_count - cluster.user_labels_count,
                    "user_labels_count": cluster.user_labels_count,
                    "choices": MultiChoiceOptionSerializer(cluster.choices.all(), many=True).data
                })
            
            logger.info(f"User '{request.user.username}' fetched {len(clusters_data)} assigned clusters at {datetime.now()}")
            
            return Response({
                "status": "success",
                "data": clusters_data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching assigned clusters for user '{request.user.username}': {str(e)}", exc_info=True)
            return Response({
                "status": "error",
                "message": "Failed to fetch assigned clusters"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskAnnotationView(generics.GenericAPIView):
    """
    View for submitting labels on individual tasks
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    serializer_class = TaskAnnotationSerializer
    
    @extend_schema(
        summary="Submit task labels",
        description="Submit multiple labels for a specific task. Reviewers can add as many labels as needed.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'task_id': {'type': 'integer', 'description': 'ID of the task to label'},
                    'labels': {
                        'type': 'array',
                        'items': {
                            'type': 'string',
                            'description': 'Individual label text'
                        },
                        'description': 'Array of labels to add to the task'
                    },
                    'notes': {
                        'type': 'string',
                        'description': 'Any notes or comments the reviewer has'
                    },
                },
                'required': ['task_id', 'labels']
            }
        },
        responses={
            200: OpenApiResponse(
                response=None,
                description="Task labels submitted successfully",
                examples=[
                    OpenApiExample(
                        "Successful Labeling",
                        value={
                            "status": "success",
                            "message": "Task labels submitted successfully",
                            "data": {
                                "task_id": 123,
                                "serial_no": "T12345",
                                "labels_added": 3,
                                "total_labels": 5,
                                "processing_status": "COMPLETED"
                            }
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                response=None,
                description="Invalid label data or task not available",
                examples=[
                    OpenApiExample(
                        "Task Not Available",
                        value={
                            "status": "error",
                            "detail": "Task is not available for labeling"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, False))
        
        task_id = serializer.validated_data.get('task_id')
        labels = serializer.validated_data.get('labels', [])
        notes = serializer.validated_data.get('notes', None)  
        
        try:
            # Validate required fields
            if not task_id:
                return Response({
                    'status': 'error',
                    'detail': 'Missing required field: task_id'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not labels or not isinstance(labels, list):
                return Response({
                    'status': 'error',
                    'detail': 'Labels must be a non-empty array'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if len(labels) == 0:
                return Response({
                    'status': 'error',
                    'detail': 'At least one label must be provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get the task            
            try:
                task = Task.objects.select_related('cluster').get(id=task_id)
            except Task.DoesNotExist:
                return Response({
                    'status': 'error',
                    'detail': 'Task not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Check if task has already been labeled by the user
            if TaskLabel.objects.filter(task=task, labeller=request.user).exists():
                return Response({
                    'status': 'error',
                    'detail': 'You have already labeled this task'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user is assigned to review this cluster
            if not task.cluster or request.user not in task.cluster.assigned_reviewers.all():
                return Response({
                    'status': 'error',
                    'detail': 'You are not assigned to review this task cluster'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if task is available for annotation
            if task.processing_status not in ['REVIEW_NEEDED', 'ASSIGNED_REVIEWER']:
                return Response({
                    'status': 'error',
                    'detail': f'Task is not available for labeling, current status: {task.processing_status}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            
            is_text_input_type = task.cluster.input_type  in [TaskInputTypeChoices.TEXT, TaskInputTypeChoices.MULTIPLE_CHOICE]

            if not is_text_input_type:
                # Validate that all labels are valid URLs
                from django.core.validators import URLValidator
                from django.core.exceptions import ValidationError

                url_validator = URLValidator()
                invalid_urls = []
                
                for label in labels:
                    try:
                        url_validator(label)
                    except ValidationError:
                        invalid_urls.append(label)
                
                if invalid_urls:
                    return Response({
                        'status': 'error',
                        'detail': f'Cannot submit plain texts for a task where the input type is {task.cluster.input_type}, please provide valid urls for the labels',
                        "invalid_urls": invalid_urls
                    }, status=status.HTTP_400_BAD_REQUEST)
            
    
            # Create TaskLabel instances for each label
            created_labels = []

            for label_text in labels:
                if label_text and label_text.strip():  # Skip empty labels
                    task_label = TaskLabel.objects.create(
                        task=task,
                        label=label_text.strip() if is_text_input_type else None,
                        label_file_url=label_text.strip() if not is_text_input_type else None,
                        labeller=request.user,
                        notes = notes
                    )
                    created_labels.append(task_label)
            
            cluster = task.cluster

            review_session, created = ManualReviewSession.objects.get_or_create(labeller=request.user, cluster=cluster)
            

            task_ids = cluster.tasks.values_list("id", flat=True) #get the ids of all the tasks in a cluster
            
            user_labelled_tasks_ids = TaskLabel.objects.filter(task_id__in=task_ids, labeller=request.user).values_list("task_id", flat=True).distinct()  #get the ids of all the tasks the currently logged in user has labelled in this cluster
            
            user_review_session_complete= set(task_ids) == set(user_labelled_tasks_ids)
            

            if user_review_session_complete:
                review_session.status = ManualReviewSessionStatusChoices.COMPLETED
                review_session.save()
                earnings, _ = LabelerEarnings.objects.get_or_create(labeler=request.user)

            
     
      
            task.human_reviewed = True
            task.save()
            
            cluster.update_completion_percentage()
            
            cluster.project.create_log(f"Reviewer '{request.user.username}' submitted {len(created_labels)} labels for task {task.serial_no} at {datetime.now()}")
            
            # Send real-time update
            push_realtime_update(task, action='task_labels_completed')
            
            logger.info(f"Reviewer '{request.user.username}' submitted {len(created_labels)} labels for task {task.serial_no} at {datetime.now()}")
            
            cache.delete_pattern(f"*project_detail_GET_/api/v1/account/projects/{cluster.project.id}/*") #invalidate project detail cache when a label is provided, this is becuase project detail depends on logs and stats from here
            return Response({
                'status': 'success',
                'message': 'Task labels submitted successfully',
                'data': {
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'labels_added': len(created_labels),
                    'total_labels': TaskLabel.objects.filter(task=task).count(),
                    'processing_status': task.processing_status,
                    # 'final_label': task.final_label,
                    'labels': [label.label for label in created_labels]
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error submitting task labels: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to submit labels: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ClusterAnnotationProgressView(APIView):
    """
    View to get annotation progress for a specific cluster
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    
    @extend_schema(
        summary="Get cluster annotation progress",
        description="Retrieve annotation progress and statistics for a specific cluster.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Cluster annotation progress",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "data": {
                                "cluster_id": 1,
                                "total_tasks": 100,
                                "completed_tasks": 75,
                                "pending_tasks": 25,
                                "completion_percentage": 75.0,
                                "assigned_reviewers": ["user1", "user2"],
                                "deadline": "2025-08-29",
                                "labeller_instructions": "Review text content for offensive language"
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    
    @cache_response_decorator('cluster_annotation_progress', per_user=True)
    def get(self, request, cluster_id):
      
        try:
            # Get the cluster
            cluster = get_object_or_404(TaskCluster, id=cluster_id)
            
            # Check if user is assigned to review this cluster
            if request.user not in cluster.assigned_reviewers.all():
                return Response({
                    'status': 'error',
                    'detail': 'You are not assigned to review this cluster'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get task statistics
            total_tasks = cluster.tasks.count()
            
            #get all the unique task labels this person has made on this cluster
            labelled_task_ids = TaskLabel.objects.filter(task__cluster=cluster, labeller=request.user).values_list('task_id', flat=True).distinct()
            total_labelled_tasks = len(set(labelled_task_ids))
            
            pending_tasks = total_tasks - total_labelled_tasks
            
            completion_percentage = (total_labelled_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Get reviewer information
            assigned_reviewers = [user.username for user in cluster.assigned_reviewers.all()]
            
            logger.info(f"User '{request.user.username}' fetched annotation progress for cluster {cluster_id} at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'cluster_id': cluster.id,
                    'total_tasks': total_tasks,
                    'completed_tasks': total_labelled_tasks,
                    'pending_tasks': pending_tasks,
                    'completion_percentage': round(completion_percentage, 2),
                    'assigned_reviewers': assigned_reviewers,
                    'deadline': cluster.deadline,
                    'labeller_instructions': cluster.labeller_instructions,
                    'input_type': cluster.input_type,
                    'task_type': cluster.task_type,
                    'annotation_method': cluster.annotation_method
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching cluster annotation progress: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to fetch cluster progress: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AvailableTasksForAnnotationView(APIView):
    """
    View to get available tasks for annotation from user's assigned clusters
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    
    @extend_schema(
        summary="Get available tasks for annotation",
        description="Retrieve tasks that are available for annotation from clusters assigned to the current user.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Available tasks for annotation",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "data": {
                                "available_tasks": [
                                    {
                                        "id": 123,
                                        "serial_no": "T12345",
                                        "task_type": "TEXT",
                                        "data": {"text": "Sample text to review"},
                                        "cluster_id": 1,
                                        "cluster_name": "Text Review Batch 1",
                                        "priority": "NORMAL"
                                    }
                                ],
                                "total_available": 25,
                                "assigned_clusters": 3
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    
    def get(self, request):
        try:
            # Get tasks available for annotation from user's assigned clusters
            available_tasks = Task.objects.filter(
                cluster__assigned_reviewers=request.user,
                processing_status__in=['REVIEW_NEEDED', 'ASSIGNED_REVIEWER'],
                assigned_to__isnull=True
            ).select_related('cluster', 'group').order_by('priority', 'created_at')
            
            # Prepare response data
            tasks_data = []
            for task in available_tasks:
                tasks_data.append({
                    'id': task.id,
                    'serial_no': task.serial_no,
                    'task_type': task.task_type,
                    'data': task.data,
                    'cluster_id': task.cluster.id,
                    'cluster_name': f"{task.cluster.task_type} Review Batch {task.cluster.id}",
                    'priority': task.priority,
                    'created_at': task.created_at,
                    'ai_confidence': task.ai_confidence,
                    'predicted_label': task.predicted_label
                })
            
            # Get cluster count
            assigned_clusters = TaskCluster.objects.filter(assigned_reviewers=request.user).count()
            
            logger.info(f"User '{request.user.username}' fetched {len(tasks_data)} available tasks for annotation at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'available_tasks': tasks_data,
                    'total_available': len(tasks_data),
                    'assigned_clusters': assigned_clusters
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching available tasks for annotation: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to fetch available tasks: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskLabelsView(APIView):
    """
    View to retrieve all labels for a specific task
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get task labels",
        description="Retrieve all labels associated with a specific task.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Task labels retrieved successfully",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "data": {
                                "task_id": 123,
                                "serial_no": "T12345",
                                "labels": [
                                    {
                                        "id": 1,
                                        "label": "positive",
                                        "labeller": "user1",
                                        "created_at": "2025-01-15T10:30:00Z"
                                    },
                                    {
                                        "id": 2,
                                        "label": "technology",
                                        "labeller": "user2",
                                        "created_at": "2025-01-15T11:00:00Z"
                                    }
                                ],
                                "total_labels": 2,
                                "unique_labellers": 2
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    
    def get(self, request, task_id):
        try:
            # Get the task
            task = get_object_or_404(Task, id=task_id)
            
            # Check if user has access to this task
            # Users can view labels if they created the task, are assigned to review it, or are assigned to the cluster
            has_access = (
                task.user == request.user or
                task.assigned_to == request.user or
                (task.cluster and request.user in task.cluster.assigned_reviewers.all())
            )
            
            if not has_access:
                return Response({
                    'status': 'error',
                    'detail': 'You do not have access to view this task'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get all labels for the task
            task_labels = TaskLabel.objects.filter(task=task).select_related('labeller').order_by('created_at')
            
            # Prepare response data
            labels_data = []
            labeller_set = set()
            
            for task_label in task_labels:
                labels_data.append({
                    'id': task_label.id,
                    'label': task_label.label,
                    'label_file_url': task_label.label_file_url,
                    'labeller': task_label.labeller.username,
                    'labeller_id': task_label.labeller.id,
                    'created_at': task_label.created_at,
                    'updated_at': task_label.updated_at
                })
                labeller_set.add(task_label.labeller.username)
            
            logger.info(f"User '{request.user.username}' fetched {len(labels_data)} labels for task {task.serial_no} at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'labels': labels_data,
                    'total_labels': len(labels_data),
                    'unique_labellers': len(labeller_set),
                    'labellers': list(labeller_set)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching task labels: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to fetch task labels: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClusterLabelsSummaryView(APIView):
    """
    View to get a summary of all labels across tasks in a cluster
    """
    permission_classes = [IsAuthenticated, IsReviewer]
    
    @extend_schema(
        summary="Get cluster labels summary",
        description="Retrieve a summary of all labels across tasks in a cluster.",
        responses={
            200: OpenApiResponse(
                response=None,
                description="Cluster labels summary",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value={
                            "status": "success",
                            "data": {
                                "cluster_id": 1,
                                "total_tasks": 10,
                                "labeled_tasks": 8,
                                "total_labels": 25,
                                "unique_labels": 15,
                                "label_frequency": {
                                    "positive": 8,
                                    "negative": 5,
                                    "technology": 12
                                },
                                "labeller_contributions": {
                                    "user1": 12,
                                    "user2": 13
                                }
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    
    def get(self, request, cluster_id):
        try:
            # Get the cluster
            cluster = get_object_or_404(TaskCluster, id=cluster_id)
            
            # Check if user is assigned to review this cluster
            if request.user not in cluster.assigned_reviewers.all():
                return Response({
                    'status': 'error',
                    'detail': 'You are not assigned to review this cluster'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get all tasks in the cluster
            cluster_tasks = cluster.tasks.all()
            total_tasks = cluster_tasks.count()
            labeled_tasks = cluster_tasks.filter(tasklabel__isnull=False).distinct().count()
            
            # Get all labels for the cluster
            cluster_labels = TaskLabel.objects.filter(task__cluster=cluster).select_related('labeller')
            total_labels = cluster_labels.count()
            
            # Calculate label frequency
            label_frequency = {}
            labeller_contributions = {}
            
            for task_label in cluster_labels:
                # Count label frequency
                label_text = task_label.label
                label_frequency[label_text] = label_frequency.get(label_text, 0) + 1
                
                # Count labeller contributions
                labeller_name = task_label.labeller.username
                labeller_contributions[labeller_name] = labeller_contributions.get(labeller_name, 0) + 1
            
            # Get unique labels count
            unique_labels = len(label_frequency)
            
            logger.info(f"User '{request.user.username}' fetched labels summary for cluster {cluster_id} at {datetime.now()}")
            
            return Response({
                'status': 'success',
                'data': {
                    'cluster_id': cluster.id,
                    'total_tasks': total_tasks,
                    'labeled_tasks': labeled_tasks,
                    'total_labels': total_labels,
                    'unique_labels': unique_labels,
                    'label_frequency': label_frequency,
                    'labeller_contributions': labeller_contributions
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching cluster labels summary: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to fetch cluster labels summary: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
