"""Sanic demo application for web-perfmonitor.

This example demonstrates the basic usage of web-perfmonitor
with a Sanic application.

Usage:
    pip install sanic web-perfmonitor[sanic]
    python sanic_demo.py

Then visit:
    http://localhost:8000/       - Fast endpoint (no alert)
    http://localhost:8000/slow   - Slow async endpoint (triggers alert)
    http://localhost:8000/api/users - API endpoint (triggers alert)
"""

import asyncio
import logging
import time

from sanic import Sanic, json, response
from sanic.request import Request

# Configure logging to see monitor output
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Import the monitor
from web_perfmonitor import MonitorConfig, PerformanceMiddleware, profile

# Create Sanic app
app = Sanic("SanicDemo")

# Configure the monitor
config = MonitorConfig(
    threshold_seconds=0.1,  # Low threshold for demo (100ms)
    alert_window_days=1,  # Short window for demo
    log_path="/tmp/perf-demo",  # Reports are always saved here
    url_blacklist=["/health", "/favicon.ico"],  # Exclude these URLs
    # Request headers collection (enabled by default)
    capture_request_headers=True,
    notice_list=[
        # Local file report (JSON/Markdown) - always enabled
  
    ],
)

# Install the middleware
middleware = PerformanceMiddleware(app, config=config)


@app.route("/")
async def index(request: Request):
    """Fast async endpoint - should not trigger alert."""
    return json({"message": "Hello, Sanic!", "status": "fast"})


@app.route("/slow")
async def slow(request: Request):
    """Slow async endpoint - will trigger performance alert."""
    await asyncio.sleep(0.2)  # 200ms delay
    return json({"message": "This was slow", "status": "slow"})


@app.route("/slow2")
async def slow2(request: Request):
    """Slow async endpoint - will trigger performance alert."""
    await asyncio.sleep(1.0)  # 1000ms delay
    return json({"message": "This was very slow", "status": "slow2"})


@app.route("/sync-slow")
def sync_slow(request: Request):
    """Slow sync endpoint - will trigger performance alert."""
    time.sleep(0.2)  # 200ms delay (blocking)
    return json({"message": "This was a slow sync operation", "status": "slow"})


@app.route("/api/users")
async def get_users(request: Request):
    """API endpoint - simulates async database query."""
    await asyncio.sleep(0.15)  # 150ms delay
    return json(
        {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ]
        }
    )


@app.route("/api/search")
async def search(request: Request):
    """Search endpoint with query parameters - test deduplication.

    Try:
        /api/search?q=hello&page=1  (triggers alert)
        /api/search?q=hello&page=2  (triggers alert - different params)
        /api/search?q=hello&page=1  (deduped - same params)
    """
    q = request.args.get("q", "")
    page = request.args.get("page", 1)
    await asyncio.sleep(0.15)  # 150ms delay
    return json({"query": q, "page": page, "results": []})


@app.route("/api/submit", methods=["POST"])
async def submit_order(request: Request):
    """POST endpoint for order submission - tests request details.

    Test with curl:
        curl -X POST http://localhost:8000/api/submit \\
             -H "Content-Type: application/json" \\
             -H "X-Request-ID: test-123" \\
             -H "X-Trace-ID: trace-456" \\
             -d '{
                   "order": "asc",
                   "offset": 0,
                   "limit": 10,
                   "keyword": "test",
                   "company_id": "123"
                 }'

    This will trigger a performance alert and generate a report with:
    - Full URL
    - Request path
    - Request method (POST)
    - Request headers (Content-Type, X-Request-ID, X-Trace-ID, etc.)
    - Request parameters (JSON body)
    """
    # Get JSON data from request
    data = request.json or {}

    # Simulate slow async database operation
    await asyncio.sleep(0.3)  # 300ms delay - exceeds threshold

    # Process the order
    order_type = data.get("order", "asc")
    offset = data.get("offset", 0)
    limit = data.get("limit", 10)
    keyword = data.get("keyword", "")
    company_id = data.get("company_id", "")

    # Return response
    return json(
        {
            "status": "success",
            "message": "Order submitted successfully",
            "data": {
                "order": order_type,
                "offset": offset,
                "limit": limit,
                "keyword": keyword,
                "company_id": company_id,
                "total_records": 42,
                "processing_time": "0.3s",
            },
        }
    )


@app.route("/health")
async def health(request: Request):
    """Health check endpoint - excluded from monitoring."""
    return json({"status": "healthy"})


# Function-level profiling example
@profile(threshold=0.05)
async def process_data_async(data: dict) -> dict:
    """Process data asynchronously with profiling enabled."""
    await asyncio.sleep(0.1)  # Simulate async processing
    return {"processed": True, "input": data}


@app.route("/process")
async def process(request: Request):
    """Endpoint that uses decorated async function."""
    result = await process_data_async({"key": "value"})
    return json(result)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Web Performance Monitor - Sanic Demo")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /              - Fast async endpoint (no alert)")
    print("  GET  /slow          - Slow async endpoint (triggers alert)")
    print("  GET  /slow2         - Very slow async endpoint (triggers alert)")
    print("  GET  /sync-slow     - Slow sync endpoint (triggers alert)")
    print("  GET  /api/users     - API endpoint (triggers alert)")
    print("  GET  /api/search?q=hello&page=1 - Test query params")
    print("  POST /api/submit    - Test POST with JSON body (triggers alert)")
    print("  GET  /process       - Uses @profile decorator")
    print("  GET  /health        - Health check (excluded)")
    print(f"\nReports will be saved to: {config.log_path}")
    print(f"Threshold: {config.threshold_seconds}s")
    print("\nTest POST endpoint:")
    print("  curl -X POST http://localhost:8000/api/submit \\")
    print('       -H "Content-Type: application/json" \\')
    print(
        '       -d \'{"order":"asc","offset":0,"limit":10,"keyword":"test","company_id":"123"}\''
    )
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=8001, debug=True)
