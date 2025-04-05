from email import message
import cohere
from dotenv import load_dotenv
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

load_dotenv()

# Initialize Cohere client with timeout settings
co = cohere.Client(
    api_key=os.getenv("CO_API_KEY"), timeout=30  # Set timeout to 30 seconds
)


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
                json_match = re.search(r'```json\s*(.*?)\s*```', response.text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    return json.loads(json_str)
                else:
                    return {
                        "label": "Normal",
                        "confidence_score": 0.0,
                        "need_human_intervention": True,
                        "justification": f"No JSON found in response",
                    }
            
            except json.JSONDecodeError:
                logger.error(f"Failed to parse response: {response.text}")
                raise

        except (Timeout, RequestException) as e:
            if attempt == max_retries - 1:  # Last attempt
                logger.error(f"Final retry failed: {str(e)}")
                return {
                    "label": "Normal",
                    "confidence_score": 0.0,
                    "need_human_intervention": True,
                    "justification": f"Error: Connection timeout after {max_retries} attempts",
                }
            logger.warning(f"Attempt {attempt + 1} failed, retrying... Error: {str(e)}")
            time.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            logger.error(f"Error in classification: {str(e)}")
            return {
                "label": "Normal",
                "confidence_score": 0.0,
                "need_human_intervention": True,
                "justification": f"Error: {str(e)}",
            }
