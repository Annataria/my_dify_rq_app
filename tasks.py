# tasks.py
import requests
import os
import time
from dotenv import load_dotenv
import logging

# Configure logging for tasks.py
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file (for local dev)
# In Docker, these will come from docker-compose.yml environment section
load_dotenv()

# --- Dify Configuration (read from environment variables) ---
DIFY_API_BASE_URL = os.getenv("DIFY_API_BASE_URL")
DIFY_APP_ID_WORKFLOW_B = os.getenv("DIFY_APP_ID_WORKFLOW_B")
DIFY_API_KEY = os.getenv("DIFY_API_KEY")

if not all([DIFY_API_BASE_URL, DIFY_APP_ID_WORKFLOW_B, DIFY_API_KEY]):
    logging.error(
        "Error: Dify API configuration variables (DIFY_API_BASE_URL, "
        "DIFY_APP_ID_WORKFLOW_B, DIFY_API_KEY) must be set."
    )
    raise ValueError("Missing Dify API configuration.")

# --- Main Task Function ---
def process_single_url_with_dify(url: str, job_id: str = "unknown", **kwargs):
    """
    This function is the "task" that an RQ worker will execute.
    It makes an API call to a Dify workflow (Workflow B) to process a single URL.

    Args:
        url (str): The single URL to be processed by Dify Workflow B.
        job_id (str): A unique identifier for the job, used for logging.
        **kwargs: Catches any unexpected keyword arguments passed to the function (e.g., from RQ).
    """
    # Log any unexpected keyword arguments for debugging
    if kwargs:
        logging.warning(
            f"Job {job_id}: process_single_url_with_dify received unexpected keyword arguments: {kwargs}"
        )

    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f"[{current_time}] Job {job_id}: Starting to process URL: {url}")

    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": {"url": url},
        "response_mode": "blocking",
        "user": f"rq_batch_user_{job_id}",
        "app_id": DIFY_APP_ID_WORKFLOW_B
    }

    try:
        response = requests.post(
            f"{DIFY_API_BASE_URL}/workflows/run",
            json=payload,
            headers=headers,
            timeout=180  # Dify API call timeout
        )
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        dify_result = response.json()
        logging.info(
            f"[{current_time}] Job {job_id}: Successfully processed URL: {url}. "
            f"Dify Result (partial): {dify_result.get('answer', 'No answer field found directly or check full result.')}"
        )

        return {
            "status": "success",
            "url": url,
            "dify_response": dify_result
        }

    except requests.exceptions.Timeout:
        logging.error(
            f"[{current_time}] Job {job_id}: Dify API call timed out for URL: {url}. "
            "This job will be retried (if configured)."
        )
        raise  # Re-raise to let RQ handle retries

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else "N/A"
        error_text = e.response.text if e.response else str(e)
        logging.error(
            f"[{current_time}] Job {job_id}: Dify API HTTP error {status_code} for URL {url}: {error_text}. "
            "This job will be retried (if configured)."
        )
        raise  # Re-raise to let RQ handle retries

    except Exception as e:
        logging.error(
            f"[{current_time}] Job {job_id}: An unexpected error occurred for URL {url}: {e}. "
            "This job will be retried (if configured)."
        )
        raise  # Re-raise to let RQ handle retries
