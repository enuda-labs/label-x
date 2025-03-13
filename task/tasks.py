from celery import shared_task
from .models import Task

@shared_task
def process_task(task_id):
    """
    Process a submitted content moderation task.
    This function handles queue prioritization and routing.
    
    Logic is losely build and will be revisted
    """
    try:
         # Optimized query using select_related to avoid multiple DB hits
        task = Task.objects.select_related('user').get(id=task_id)       
        # Update status to processing
        task.status = 'PROCESSING'
        task.save()
        
        # Next now is Queue priority
        if task.priority == 'URGENT':
            # we process immediately for urgent task.
            print('Priory is very  high calling function')
            route_task_to_processing(task)
        else:
            # follow queue for normal or low priority
            queue_task_for_processing(task)
            pass
            
        return {'status': 'success', 'task_id': task_id}
    
    except Task.DoesNotExist:
        return {'status': 'error', 'message': f'Task {10} not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def route_task_to_processing(task):
    """
    Route the task to either AI processing or human review based on task type and priority.
    
    I made some assumptions though
    """
    # Update task status
    print("function has been called for processing.")
    task.status = 'PROCESSING'
    task.save()
    
    # Here we would call the AI model processing
    # For now, we'll just simulate by queuing another Celery task
    # process_with_ai_model.delay(task.task_id)

def queue_task_for_processing(task):
    """
    Queue the task for processing based on priority.
    """
    # This would typically involve setting queue priorities in Celery
    # For demonstration, we'll simply call the AI model processing with a delay
    process_with_ai_model.apply_async(
        args=[task.id],
        countdown=10 if task.priority == 'NORMAL' else 30  # Delay based on priority
    )

@shared_task
def process_with_ai_model(task_id):
    """
    A place holder function for task processing. 
    """
        
    # I just update status for now since no actual model implementation.
    task = Task.objects.select_related('user').get(id=task_id)
    task.status = 'AI_REVIEWED'
    task.save()
    

    return {'status': 'success', 'task_id': task.id, 'message': 'Processed by AI model'}