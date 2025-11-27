"""Flask demo application for web-perfmonitor.

This example demonstrates the basic usage of web-perfmonitor
with a Flask application.

Usage:
    pip install flask web-perfmonitor
    python flask_demo.py

Then visit:
    http://localhost:5000/       - Fast endpoint (no alert)
    http://localhost:5000/slow   - Slow endpoint (triggers alert)
    http://localhost:5000/api/users - API endpoint (triggers alert)
"""

import logging
import time

from flask import Flask, jsonify, request

# Configure logging to see monitor output
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Import the monitor
from web_perfmonitor import MonitorConfig, PerformanceMiddleware, profile

# Create Flask app
app = Flask(__name__)

# Configure the monitor
config = MonitorConfig(
    threshold_seconds=0.1,  # Low threshold for demo (100ms)
    alert_window_days=1,  # Short window for demo
    log_path="/tmp/perf-demo",  # Reports are always saved here (mandatory)
    url_blacklist=["/health", "/favicon.ico"],  # Exclude these URLs
    # notice_list is for EXTERNAL notifiers only (Mattermost, Email, Slack, etc.)
    # Local report saving is automatic and mandatory
    notice_list=[
        # 163 Email notification
        {
            "type": "email",
            "format": "html",
            "smtp_host": "smtp.163.com",
            "smtp_port": 465,
            "username": "xxxxxxx@163.com",
            "password": "xxxxxxx",
            "sender": "xxxxxxx@163.com",
            "recipients": ["xxxxxxx@163.com"],
            "use_ssl": True,
            "use_tls": False,
            "subject_prefix": "[性能告警]"
        }
        # Uncomment to enable Mattermost notifications:
        # {
        #     "type": "mattermost",
        #     "format": "markdown",
        #     "server_url": "https://mattermost.example.com",
        #     "token": "your-token",
        #     "channel_id": "your-channel-id",
        # }
    ],
)

# Install the middleware
middleware = PerformanceMiddleware(app, config=config)


@app.route("/")
def index():
    """Fast endpoint - should not trigger alert."""
    return jsonify({"message": "Hello, World!", "status": "fast"})


@app.route("/slow")
def slow():
    """Slow endpoint - will trigger performance alert."""
    time.sleep(0.2)  # 200ms delay
    return jsonify({"message": "This was slow", "status": "slow"})

@app.route("/slow2")
def slow2():
    """Slow endpoint - will trigger performance alert."""
    time.sleep(1.0)  # 200ms delay
    return jsonify({"message": "This was slow2", "status": "slow2"})


@app.route("/api/users")
def get_users():
    """API endpoint - simulates database query."""
    time.sleep(0.15)  # 150ms delay
    return jsonify(
        {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]
        }
    )


@app.route("/api/search")
def search():
    """Search endpoint with query parameters - test deduplication.

    Try:
        /api/search?q=hello&page=1  (triggers alert)
        /api/search?q=hello&page=2  (triggers alert - different params)
        /api/search?q=hello&page=1  (deduped - same params)
    """
    q = request.args.get("q", "")
    page = request.args.get("page", 1)
    time.sleep(0.15)  # 150ms delay
    return jsonify({"query": q, "page": page, "results": []})


@app.route("/api/submit", methods=["POST"])
def submit_order():
    """POST endpoint for order submission - tests request details in MD report.

    Test with curl:
        curl -X POST http://localhost:5000/api/submit \\
             -H "Content-Type: application/json" \\
             -d '{
                   "order": "asc",
                   "offset": 0,
                   "limit": 10,
                   "keyword": "38.38.250.207:39924",
                   "target_company_id": [],
                   "company_id": "28711512"
                 }'

    This will trigger a performance alert and generate a report with:
    - Full URL
    - Request path
    - Request method (POST)
    - Request parameters (JSON body)
    """
    # Get JSON data from request
    data = request.get_json() or {}

    # Simulate slow database operation
    time.sleep(0.3)  # 300ms delay - exceeds threshold

    # Process the order
    order_type = data.get("order", "asc")
    offset = data.get("offset", 0)
    limit = data.get("limit", 10)
    keyword = data.get("keyword", "")
    company_id = data.get("company_id", "")

    # Return response
    return jsonify({
        "status": "success",
        "message": "Order submitted successfully",
        "data": {
            "order": order_type,
            "offset": offset,
            "limit": limit,
            "keyword": keyword,
            "company_id": company_id,
            "total_records": 42,
            "processing_time": "0.3s"
        }
    })


@app.route("/health")
def health():
    """Health check endpoint - excluded from monitoring."""
    return jsonify({"status": "healthy"})


# Function-level profiling example
@profile(threshold=0.05)
def process_data(data: dict) -> dict:
    """Process data with profiling enabled."""
    time.sleep(0.1)  # Simulate processing
    return {"processed": True, "input": data}


@app.route("/process")
def process():
    """Endpoint that uses decorated function."""
    result = process_data({"key": "value"})
    return jsonify(result)


@app.teardown_appcontext
def shutdown_monitor(exception=None):
    """Cleanup on app shutdown."""
    # Note: In production, use atexit or signal handlers
    pass


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Web Performance Monitor Demo")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /              - Fast endpoint (no alert)")
    print("  GET  /slow          - Slow endpoint (triggers alert)")
    print("  GET  /api/users     - API endpoint (triggers alert)")
    print("  GET  /api/search?q=hello&page=1 - Test query params")
    print("  POST /api/submit    - Test POST with JSON body (triggers alert)")
    print("  GET  /process       - Uses @profile decorator")
    print("  GET  /health        - Health check (excluded)")
    print(f"\nReports will be saved to: {config.log_path}")
    print(f"Threshold: {config.threshold_seconds}s")
    print("\nTest POST endpoint:")
    print("  curl -X POST http://localhost:5000/api/submit \\")
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"order":"asc","offset":0,"limit":10,"keyword":"test","company_id":"123"}\'')
    print("=" * 60 + "\n")

    app.run(debug=True, port=5000)
