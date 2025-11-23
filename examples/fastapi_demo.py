"""FastAPI demo application for web-perfmonitor.

This demo showcases the performance monitoring capabilities with FastAPI.
Run with: uvicorn examples.fastapi_demo:app --reload
Or: python examples/fastapi_demo.py

Available endpoints:
    GET /            - Quick response (under threshold)
    GET /slow        - Slow async response (triggers alert)
    GET /slow-sync   - Slow sync response (triggers alert)
    GET /api/data    - API endpoint with moderate delay
    GET /api/search  - Search with query parameters
    POST /api/submit - POST endpoint with JSON body
    GET /health      - Health check (excluded from monitoring)
"""

import asyncio
import time
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from web_perfmonitor import MonitorConfig, PerformanceMiddleware, profile

# Create FastAPI application
app = FastAPI(
    title="FastAPI Performance Monitor Demo",
    description="Demo application showcasing web-perfmonitor with FastAPI",
    version="0.1.0",
)

# Configure performance monitoring
config = MonitorConfig(
    threshold_seconds=0.5,  # Alert when response time > 0.5s
    alert_window_days=10,  # Deduplicate alerts for 10 days
    log_path="/tmp/fastapi_perf_reports",  # Where to save reports
    url_blacklist=["/health", "/docs", "/redoc", "/openapi.json"],  # Skip monitoring
    notice_list=[
        # 163 Email notification
        {
            "type": "email",
            "format": "html",
            "smtp_host": "smtp.163.com",
            "smtp_port": 465,
            "username": "example@163.com",
            "password": "xxxxxxxxxx",
            "sender": "example@163.com",
            "recipients": ["example@163.com"],
            "use_ssl": True,
            "use_tls": False,
            "subject_prefix": "[性能告警]"
        }
    ]
)

# Install the middleware - auto-detects FastAPI
PerformanceMiddleware(app, config=config)


# Request/Response models
class SubmitData(BaseModel):
    """Data model for POST requests."""

    name: str
    value: int
    tags: list[str] = []


class SearchResult(BaseModel):
    """Data model for search results."""

    query: str
    results: list[dict]
    total: int


# Routes


@app.get("/")
async def root() -> dict:
    """Quick endpoint - should not trigger alerts."""
    return {"message": "Hello World", "status": "fast"}

async def slow1():
    await asyncio.sleep(1.5)
    return True

async def slow2():
    await asyncio.sleep(0.5)
    return True

@app.get("/slow")
async def slow_endpoint() -> dict:
    """Slow async endpoint - will trigger performance alert.

    Simulates a slow database query or external API call.
    """
    # Simulate slow async operation
    await slow1()
    await slow2()
    return {"message": "This was slow", "duration": "1 second"}


@app.get("/slow-sync")
def slow_sync_endpoint() -> dict:
    """Slow sync endpoint - will also trigger performance alert.

    FastAPI can handle both sync and async routes.
    """
    # Simulate slow sync operation (e.g., CPU-bound task)
    time.sleep(0.8)
    return {"message": "Sync slow operation", "duration": "0.8 seconds"}


@app.get("/api/data")
async def get_data() -> dict:
    """API endpoint with moderate delay.

    May or may not trigger alert depending on threshold.
    """
    # Simulate moderate database query
    await asyncio.sleep(0.3)

    return {
        "data": [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"},
        ],
        "count": 3,
    }


@app.get("/api/search", response_model=SearchResult)
async def search(
    q: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Results per page"),
) -> SearchResult:
    """Search endpoint with query parameters.

    Tests that query parameters are captured in metadata.
    """
    # Simulate search operation
    await asyncio.sleep(0.4)

    return SearchResult(
        query=q,
        results=[
            {"id": i, "name": f"Result {i} for '{q}'"} for i in range(1, limit + 1)
        ],
        total=100,
    )


@app.post("/api/submit")
async def submit_data(data: SubmitData) -> dict:
    """POST endpoint for data submission.

    Tests that request body is handled correctly.
    """
    # Simulate data processing
    await asyncio.sleep(0.6)

    return {
        "status": "accepted",
        "received": data.model_dump(),
        "message": f"Processed {data.name} with value {data.value}",
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint - excluded from monitoring.

    This endpoint is in the URL blacklist and won't be profiled.
    """
    return {"status": "healthy"}


@app.get("/api/users/{user_id}")
async def get_user(user_id: int) -> dict:
    """Endpoint with path parameters.

    Tests that path parameters work correctly.
    """
    await asyncio.sleep(0.2)
    return {"user_id": user_id, "name": f"User {user_id}"}


# Function-level profiling example


@profile(threshold=0.1, name="expensive_calculation")
async def expensive_calculation(n: int) -> int:
    """Expensive async calculation with function-level profiling.

    Uses the @profile decorator for fine-grained monitoring.
    """
    await asyncio.sleep(0.2)
    return sum(i * i for i in range(n))


@app.get("/api/calculate/{n}")
async def calculate(n: int) -> dict:
    """Endpoint using function-level profiling."""
    result = await expensive_calculation(n)
    return {"n": n, "result": result}


if __name__ == "__main__":
    import uvicorn

    print("Starting FastAPI Performance Monitor Demo...")
    print("Available endpoints:")
    print("  GET  /            - Quick response")
    print("  GET  /slow        - Slow async response (triggers alert)")
    print("  GET  /slow-sync   - Slow sync response (triggers alert)")
    print("  GET  /api/data    - API data endpoint")
    print("  GET  /api/search  - Search with query params")
    print("  POST /api/submit  - Submit JSON data")
    print("  GET  /health      - Health check (excluded)")
    print("  GET  /api/users/{id} - User endpoint")
    print("  GET  /api/calculate/{n} - Calculation endpoint")
    print()
    print("Reports will be saved to: /tmp/fastapi_perf_reports")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8001)
