import cohere
from dotenv import load_dotenv
import os
import json
import time
from requests.exceptions import Timeout, RequestException
import requests
import logging

# Set up logger
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Cohere client with timeout settings
co = cohere.Client(
    api_key=os.getenv("CO_API_KEY"),
    timeout=30  # Set timeout to 30 seconds
)

def text_classification(text, max_retries=3):
    for attempt in range(max_retries):
        logger.info(f'Attempting text classification, attempt {attempt + 1} of {max_retries}')

        try:
            # Define the conversation with system configuration for classification
            response = co.chat(
                model="command-a-03-2025",  # Using standard model instead of command-a-03-2025
                message=text,
                chat_history=[
                    {
                        "role": "system",
                        "message": """You are a text classification AI designed to categorize messages into different levels of offensiveness. 
                        You classify text into one of three categories:
                        - Very Offensive
                        - Less Offensive
                        - Normal 

                        Your response format should always be in JSON with the following fields:
                        {
                            "label": "<classification_label>",
                            "confidence_score": <confidence_value_between_0_and_1>,
                            "need_human_intervention": <true_or_false>,
                            "justification": "<short_explanation_for_the_classification>"
                        }

                        Guidelines:
                        - If the text contains hate speech, explicit threats, or highly offensive language, classify it as "Very Offensive".
                        - If the text contains mild insults or potentially inappropriate language but not extreme, classify it as "Less Offensive".
                        - If the text is neutral or respectful, classify it as "Normal".
                        - If confidence score is below 0.5, set "need_human_intervention" to true.
                        - Keep justification concise and explain why the classification was made.
                        """
                    }
                ]
            )
            
            try:            
                response_text = response.text.replace('```json', '').replace('```', '')
                return json.loads(response_text)
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
                    "justification": f"Error: Connection timeout after {max_retries} attempts"
                }
            logger.warning(f"Attempt {attempt + 1} failed, retrying... Error: {str(e)}")
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except Exception as e:
            logger.error(f"Error in classification: {str(e)}")
            return {
                "label": "Normal",
                "confidence_score": 0.0,
                "need_human_intervention": True,
                "justification": f"Error: {str(e)}"
            }
