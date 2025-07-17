import json
from celery import shared_task
from celery.utils.log import get_task_logger

from account.models import CustomUser
from task.utils import push_realtime_update

from .ai_processor import submit_human_review, text_classification
from .models import Task, UserReviewChatHistory
from .utils import assign_reviewer, dispatch_review_response_message


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
        task = Task.objects.select_related("user").get(id=task_id)
        logger.debug(f"Retrieved task {task_id}")

        # Update status to processing
        task.processing_status = "PROCESSING"
        task.save()

        push_realtime_update(task, action="task_status_changed")
        logger.info(f"Updated task {task_id} status to PROCESSING")

        # Get priority with fallback to 'NORMAL'
        priority = getattr(task, "priority", "NORMAL")
        logger.info(f"Task {task_id} priority: {priority}")

        # Next now is Queue priority
        if priority == "URGENT":
            logger.info(f"Task {task_id} is URGENT priority, processing immediately")
            route_task_to_processing.delay(task_id)
        else:
            logger.info(f"Task {task_id} is {priority} priority, queuing normally")
            queue_task_for_processing.delay(task_id)

        return {"status": "success", "task_id": task_id}

    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found in database")
        return {"status": "error", "message": f"Task {task_id} not found"}
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@shared_task
def route_task_to_processing(task_id):
    """
    Route the task to either AI processing or human review based on task type and priority.

    I made some assumptions though
    """
    logger.info(f"Starting to route task {task_id}")

    try:
        task = Task.objects.select_related("user").get(id=task_id)
        logger.debug(f"Retrieved task {task_id} for routing")

        task.processing_status = "PROCESSING"
        task.save()

        push_realtime_update(task, action="task_status_changed")
        logger.info(f"Updated task {task_id} status to PROCESSING")

        # Call AI processing
        logger.info(f"Initiating AI processing for task {task_id}")
        process_with_ai_model.delay(task_id)

        return {"status": "success", "task_id": task_id}
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
        task = Task.objects.select_related("user").get(id=task_id)
        logger.debug(f"Retrieved task {task_id} with priority {task.priority}")

        # Set delay based on priority
        delay_time = 10 if task.priority == "NORMAL" else 30  # Delay based on priority
        logger.info(f"Setting delay of {delay_time} seconds for task {task_id}")

        # Queue the task with appropriate delay
        process_with_ai_model.apply_async(args=[task.id], countdown=delay_time)
        logger.info(f"Successfully queued task {task_id} with {delay_time}s delay")

        return {"status": "success", "task_id": task_id}
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
        task = Task.objects.select_related("user").get(id=task_id)

        # Only update if still in PROCESSING state
        if task.processing_status == "PROCESSING":
            classification = text_classification(task.data)
            logger.info(f"AI classification result: {classification}")

            task.processing_status = "AI_REVIEWED"

            task.predicted_label = classification["classification"]
            task.human_reviewed = classification["requires_human_review"]
            task.ai_output = classification
            task.save()

            # push_realtime_update(task)
            logger.info(f"Completed AI processing for task {task_id}")

            # If human review is needed, try to assign a reviewer
            if classification["requires_human_review"]:
                logger.info(f"We are in require human intelligence")
                task.processing_status = "REVIEW_NEEDED"
                task.review_status = "PENDING_REVIEW"
                task.save()
                task.create_log(f"Task {task.id} status changed to REVIEW_NEEDED ")
                push_realtime_update(task, action="task_status_changed")
            else:
                task.processing_status = "COMPLETED"
                task.final_label = classification.get("classification", None)
                task.ai_confidence = float(classification.get('confidence', classification.get('confidence_score', 0.0)))
                task.save()
                task.create_log(f"Task {task.id} successfully reviewed by AI status: COMPLETED")
                push_realtime_update(task, action="task_status_changed")
                logger.info(f"Task {task_id} completed automatically")

        return {"status": "success", "task_id": task.id}
    except Exception as e:
        logger.error(
            f"Error in AI processing for task {task_id}: {str(e)}", exc_info=True
        )
        raise


@shared_task
def submit_human_review_history(
    reviewer_id, task_id, confidence_score, justification, classification
):
    try:
        task = Task.objects.select_related("user").get(id=int(task_id))
        reviewer = CustomUser.objects.get(id=reviewer_id)

        last_human_review = (
            UserReviewChatHistory.objects.filter(task=task)
            .order_by("-created_at")
            .first()
        )

        review_history = UserReviewChatHistory.objects.create(
            reviewer=reviewer,
            task=task,
            human_confidence_score=float(confidence_score),
            human_justification=justification,
            human_classification=classification,
        )

        if last_human_review:
            success, ai_response = submit_human_review(
                task.data,
                last_human_review.ai_output.get("corrected_classification"),
                classification,
                justification,
            )
        else:
            success, ai_response = submit_human_review(
                task.data,
                task.ai_output.get("classification"),
                classification,
                justification,
            )

        if success:
            review_history.ai_output = ai_response
            review_history.save()
            # respond to the frontend websocket
            dispatch_review_response_message(reviewer.id, ai_response)
        else:
            dispatch_review_response_message(
                reviewer.id, {"error": True, "message": ai_response}
            )
    except Exception as e:
        print(e)
        logger.info(f"Error submitting feedback for task {str(e)}")


@shared_task
def provide_feedback_to_ai_model(task_id, review):
    """
    Provide feedback to the AI Model
    """
    logger.info(f"Starting Feedback processing for task {task_id}")

    try:
        task = Task.objects.select_related("user").get(id=task_id)
        # strinify the review before sending to the api
        json_string = json.dumps(review, indent=2)
        classification = text_classification(json_string)
        task.processing_status = "COMPLETED"
        task.review_status = "PENDING_APPROVAL"
        task.human_reviewed = True
        task.final_label = classification.get("classification")
        task.ai_output = classification
        task.save()

        push_realtime_update(task, action="task_status_changed")
        logger.info(f"Feedback completed for task with ID {task.id}")

        return {"status": "success", "task_id": task.id}
    except Exception as e:
        logger.error(
            f"Error processing feedback for task {task.id }: {str(e)}", exc_info=True
        )
        raise
