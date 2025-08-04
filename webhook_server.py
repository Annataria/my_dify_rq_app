# webhook_server.py
import os
import uuid
from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue, Retry
from dotenv import load_dotenv
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file (for local dev)
# In Docker, these will come from docker-compose.yml environment section
load_dotenv()

# Get Redis URL from environment variables
REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    logging.error("REDIS_URL environment variable is not set.")
    sys.exit(1)  # Exit if essential config is missing

# Connect to Redis
try:
    redis_conn = Redis.from_url(REDIS_URL)
    redis_conn.ping()  # Test connection
    logging.info("Successfully connected to Redis.")
except Exception as e:
    logging.error(f"Failed to connect to Redis: {e}")
    sys.exit(1)

# Import the task function from tasks.py (assuming tasks.py is in the same directory)
try:
    from tasks import process_single_url_with_dify
    logging.info("Successfully imported process_single_url_with_dify from tasks.py.")
except ImportError as e:
    logging.error(f"Failed to import tasks.py or process_single_url_with_dify: {e}")
    sys.exit(1)

app = Flask(__name__)

# Basic health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    try:
        redis_conn.ping()
        return jsonify({"status": "ok", "redis_status": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "redis_status": "disconnected", "error": str(e)}), 500

@app.route('/enqueue_urls_webhook', methods=['POST'])
def enqueue_urls_webhook():
    data = request.get_json()
    if not data:
        logging.warning("Received empty or non-JSON request.")
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    # Get the key containing the URLs, defaults to 'urls'
    urls_data_key = os.getenv("DIFY_WEBHOOK_URLS_KEY", "urls")
    urls_to_process = data.get(urls_data_key)

    if not isinstance(urls_to_process, list):
        logging.error(f"Expected a list of URLs in key '{urls_data_key}', but received: {type(urls_to_process)} - {urls_to_process}")
        return jsonify({"status": "error", "message": f"Expected a list of URLs in key '{urls_data_key}'"}), 400

    if not urls_to_process:
        logging.warning("Received an empty list of URLs from Dify.")
        return jsonify({"status": "success", "message": "No URLs to enqueue."}), 200

    q = Queue(connection=redis_conn)
    enqueued_count = 0
    for url in urls_to_process:
        if not isinstance(url, str):
            logging.warning(f"Skipping non-string item found in URL list: {url}")
            continue
        try:
            job_id = f"webhook_processor_{uuid.uuid4().hex}"
            q.enqueue(
                process_single_url_with_dify,
                url,
                job_id=job_id,
                result_ttl=86400,
                failure_ttl=604800,
                retry=Retry(max=3, interval=[10, 30, 60]),
                timeout=300,
            )
            enqueued_count += 1
            logging.info(f"Enqueued job {job_id} for URL: {url}")
        except Exception as e:
            logging.error(f"Failed to enqueue URL {url}: {e}")

    logging.info(f"Received {len(urls_to_process)} URLs. Successfully enqueued {enqueued_count} jobs.")
    return jsonify({"status": "success", "enqueued_count": enqueued_count}), 200

if __name__ == '__main__':
    # You can get the host/port from environment variables for flexibility
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")  # Listen on all interfaces
    port = int(os.getenv("WEBHOOK_PORT", 5000))  # Default Flask port
    logging.info(f"Starting webhook server on http://{host}:{port}")
    # Use debug=True for development (auto-reloads), but NOT in production!
    app.run(host=host, port=port, debug=False)
