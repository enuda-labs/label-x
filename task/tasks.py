from celery import shared_task
from celery.utils.log import get_task_logger

from task.utils import dispatch_task_message, push_realtime_update

from .ai_processor import text_classification
from .models import Task
from .utils import assign_reviewer


# Set up logger
logger = get_task_logger(__name__)

@shared_task
def process_task(task_id):
    """
    Process a submitted content moderation task.
    This function handles queue prioritization and routing.
    """
    logger.info(f"Starting to process task {task_id}")
    
    try:
        # Optimized query using select_related to avoid multiple DB hits
        task = Task.objects.select_related('user').get(id=task_id)       
        logger.debug(f"Retrieved task {task_id}")
        
        # Update status to processing
        task.status = 'PROCESSING'
        task.save()
        
        push_realtime_update(task)
        logger.info(f"Updated task {task_id} status to PROCESSING")
        
        # Get priority with fallback to 'NORMAL'
        priority = getattr(task, 'priority', 'NORMAL')
        logger.info(f"Task {task_id} priority: {priority}")
        
        # Next now is Queue priority
        if priority == 'URGENT':
            logger.info(f"Task {task_id} is URGENT priority, processing immediately")
            route_task_to_processing.delay(task_id)
        else:
            logger.info(f"Task {task_id} is {priority} priority, queuing normally")
            queue_task_for_processing.delay(task_id)
            
        return {'status': 'success', 'task_id': task_id}
    
    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found in database")
        return {'status': 'error', 'message': f'Task {task_id} not found'}
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        return {'status': 'error', 'message': str(e)}

@shared_task
def route_task_to_processing(task_id):
    """
    Route the task to either AI processing or human review based on task type and priority.
    
    I made some assumptions though
    """
    logger.info(f"Starting to route task {task_id}")
    
    try:
        task = Task.objects.select_related('user').get(id=task_id)
        logger.debug(f"Retrieved task {task_id} for routing")
        
        task.status = 'PROCESSING'
        task.save()
        
        push_realtime_update(task)
        logger.info(f"Updated task {task_id} status to PROCESSING")
        
        # Call AI processing
        logger.info(f"Initiating AI processing for task {task_id}")
        process_with_ai_model.delay(task_id)
        
        return {'status': 'success', 'task_id': task_id}
    except Exception as e:
        logger.error(f"Error routing task {task_id}: {str(e)}", exc_info=True)
        raise

@shared_task
def queue_task_for_processing(task_id):
    """
    Queue the task for processing based on priority.
    """
    logger.info(f"Queueing task {task_id} for processing")
    
    try:
        task = Task.objects.select_related('user').get(id=task_id)
        logger.debug(f"Retrieved task {task_id} with priority {task.priority}")
        
        # Set delay based on priority
        delay_time = 10 if task.priority == 'NORMAL' else 30  # Delay based on priority
        logger.info(f"Setting delay of {delay_time} seconds for task {task_id}")
        
        # Queue the task with appropriate delay
        process_with_ai_model.apply_async(
            args=[task.id],
            countdown=delay_time
        )
        logger.info(f"Successfully queued task {task_id} with {delay_time}s delay")
        
        return {'status': 'success', 'task_id': task_id}
    except Exception as e:
        logger.error(f"Error queueing task {task_id}: {str(e)}", exc_info=True)
        raise

@shared_task
def process_with_ai_model(task_id):
    """
    Process the task using AI model and handle reviewer assignment if needed.
    """
    logger.info(f"Starting AI processing for task {task_id}")
    
    try:
        task = Task.objects.select_related('user').get(id=task_id)
        
        # Only update if still in PROCESSING state
        if task.status == 'PROCESSING':
            classification = text_classification(task.data)
            logger.info(f"AI classification result: {classification}")
            
            task.status = 'AI_REVIEWED'
            task.predicted_label = classification['classification']
            task.human_reviewed = classification['requires_human_review']
            task.ai_output = classification
            task.save()
            
            push_realtime_update(task)
            logger.info(f"Completed AI processing for task {task_id}")
            
            # If human review is needed, try to assign a reviewer
            if classification['requires_human_review']:
                logger.info(f"We are in require human intelligence")
                if assign_reviewer(task):
                    logger.info(f"Task {task_id} assigned to reviewer")
                else:
                    logger.warning(f"No available reviewers for task {task_id}")
                    task.status = 'PENDING_REVIEWER'
                    task.save()
                    push_realtime_update(task)
            else:
                task.status = 'COMPLETED'
                task.save()
                push_realtime_update(task)
                logger.info(f"Task {task_id} completed automatically")
        
        return {'status': 'success', 'task_id': task.id}
    except Exception as e:
        logger.error(f"Error in AI processing for task {task_id}: {str(e)}", exc_info=True)
        raise