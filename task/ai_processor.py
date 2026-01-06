from email import message
from pickle import FALSE
import cohere
from decouple import config
import os
import json
import time
from requests.exceptions import Timeout, RequestException
import requests
import logging

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import re

# Set up logger
logger = logging.getLogger(__name__)

# Initialize Cohere client with timeout settings
co = cohere.Client(
    api_key=config("CO_API_KEY", default=""), timeout=30  # Set timeout to 30 seconds
)


def submit_human_review(original_text, original_classification, correct_classification, justification, max_retries=3):
    for attempt in range(max_retries):
        logger.info(f"Attempting text")
        feedback_prompt = f"""
        I'm providing human review feedback for a text classification you previously analyzed.

        ### Original Analysis
        - Text: "{original_text}"
        - Your classification: "{original_classification}"

        ### Human Review Correction
        - Correct classification: "{correct_classification}"
        - Justification: "{justification}"

        ### Learning Instructions
        1. Please analyze the difference between your classification and the human-provided correction.
        2. Update your understanding of what constitutes "{correct_classification}" content.
        3. Respond with a confirmation that you've registered this feedback and explain how you'll apply this learning to similar content in the future.
        4. Provide an updated confidence score for this classification now that you have human guidance.

        ### Output Format (JSON):
        ```json
        {{
            "text": "<INPUT_TEXT>",
            "original_classification": "<Your original classification>",
            "corrected_classification": "<Human-provided classification>",
            "learning_summary": "<Your analysis of what you learned from this correction>",
            "updated_confidence": <0.00 - 1.00>,
            "similar_examples": ["<Brief descriptions of similar text patterns you'll now classify correctly>"]
        }}
        ```
        """
        
        # Submit the feedback to the model
        response = co.chat(
            model="command-a-03-2025",
            message="Please process this human review feedback",
            chat_history=[
                {
                    "role": "system", 
                    "message": feedback_prompt
                }
            ],
        )
        
        try:
            # response_text = response.text.replace("```json", "").replace("```", "")
            json_match = re.search(
                r"```json\s*(.*?)\s*```", response.text, re.DOTALL
            )
            if json_match:
                json_str = json_match.group(1)
                print("processed ai response is", json_str)
                return True, json.loads(json_str)
            else:
                return False, "Error processing ai response"
        except json.JSONDecodeError:
            logger.error(f"Failed to parse response: {response.text}")
            return False, response.text
               
        except (Timeout, RequestException) as e:
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Cohere API final retry failed for human review submission: {str(e)}", exc_info=True)
                return False, str(e)
            logger.warning(f"Cohere API attempt {attempt + 1} failed for human review, retrying... Error: {str(e)}")
            time.sleep(2**attempt)  # Exponential backoff            
        except Exception as e:
            logger.error(f"Unexpected error in human review submission: {str(e)}", exc_info=True)
            return False, str(e)


def text_classification(text, max_retries=3):
    for attempt in range(max_retries):
        logger.info(
            f"Attempting text classification, attempt {attempt + 1} of {max_retries}"
        )

        try:
            ai_prompt = """
            You are an AI text moderation assistant. Your task is to analyze the following text and determine if it contains insults, offensive language, or foul words.  

            ### *Instructions:*
            1. *Classify* whether the text is:
            - *Safe* (No insults or offensive language)
            - *Mildly Offensive* (Mild insults, possibly harmful)
            - *Highly Offensive* (Hate speech, strong profanity, severe insults)
            
            2. *Provide a confidence score* between 0 and 1 (e.g., 0.95 means very confident).
            
            3. *If confidence < 0.80, require human review*:
            - Flag the text for manual review.
            - Allow the human reviewer to correct the classification.
            - Require the reviewer to justify their correction.  

            4. *Output Format (JSON)*:
            ```json
            {
                "text": "<INPUT_TEXT>",
                "classification": "<Safe | Mildly Offensive | Highly Offensive>",
                "confidence": <0.00 - 1.00>,
                "requires_human_review": <true | false>,
                "human_review": {
                "correction": "<Optional - if corrected>",
                "justification": "<Optional - reviewer must provide this if corrected>"
                }
            }
            ```
            
            5. Respond with only JSON, dont ask questions, classify whatever text you get
                        
            """

            # Define the conversation with system configuration for classification
            response = co.chat(
                model="command-a-03-2025",  # Using standard model instead of command-a-03-2025
                message=text,
                chat_history=[
                    {
                        "role": "system",
                        "message": ai_prompt,
                    }
                ],
            )

            try:
                # response_text = response.text.replace("```json", "").replace("```", "")
                json_match = re.search(
                    r"```json\s*(.*?)\s*```", response.text, re.DOTALL
                )
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                else:
                    return {
                        "label": "Normal",
                        "confidence_score": 0.0,
                        "need_human_intervention": True,
                        "justification": f"No JSON found in response",
                        "classification": None,
                        "requires_human_review": True
                    }

            except json.JSONDecodeError:
                logger.error(f"Failed to parse response: {response.text}")
                raise

        except (Timeout, RequestException) as e:
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Cohere API final retry failed for text classification: {str(e)}", exc_info=True)
                return {
                    "label": "Normal",
                    "confidence_score": 0.0,
                    "need_human_intervention": True,
                    "justification": f"Error: Connection timeout after {max_retries} attempts",
                    "classification": None,
                    "requires_human_review": True

                }
            logger.warning(f"Cohere API attempt {attempt + 1} failed for text classification, retrying... Error: {str(e)}")
            time.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"Unexpected error in text classification: {str(e)}", exc_info=True)
            return {
                "label": "Normal",
                "confidence_score": 0.0,
                "need_human_intervention": True,
                "justification": f"Error: {str(e)}",
                "classification": None,
                "requires_human_review": True


            }
