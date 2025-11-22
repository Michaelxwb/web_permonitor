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

from flask import Flask, jsonify

# Configure logging to see monitor output
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Import the monitor
from web_perf_monitor import MonitorConfig, PerformanceMiddleware, profile

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
            "username": "example@163.com",
            "password": "xxxxxxxx",
            "sender": "example@163.com",
            "recipients": ["example@163.com"],
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
    from flask import request

    q = request.args.get("q", "")
    page = request.args.get("page", 1)
    time.sleep(0.15)  # 150ms delay
    return jsonify({"query": q, "page": page, "results": []})


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
    print("  GET /        - Fast endpoint (no alert)")
    print("  GET /slow    - Slow endpoint (triggers alert)")
    print("  GET /api/users - API endpoint (triggers alert)")
    print("  GET /api/search?q=hello&page=1 - Test query param deduplication")
    print("  GET /process - Uses @profile decorator")
    print("  GET /health  - Health check (excluded)")
    print(f"\nReports will be saved to: {config.log_path}")
    print(f"Threshold: {config.threshold_seconds}s")
    print("=" * 60 + "\n")

    app.run(debug=True, port=5000)
