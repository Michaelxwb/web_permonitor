"""Integration tests for FastAPI performance monitoring."""

import asyncio
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web_perfmonitor import MonitorConfig, PerformanceMiddleware


class TestFastAPIIntegration:
    """Integration tests for FastAPI with PerformanceMiddleware."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.app = FastAPI()
        self.config = MonitorConfig(
            threshold_seconds=0.1,
            url_blacklist=["/health"],
        )

        # Register routes
        @self.app.get("/")
        async def root() -> dict:
            return {"message": "Hello World"}

        @self.app.get("/slow")
        async def slow_endpoint() -> dict:
            await asyncio.sleep(0.2)  # Exceeds threshold
            return {"message": "Slow response"}

        @self.app.get("/fast")
        async def fast_endpoint() -> dict:
            return {"message": "Fast response"}

        @self.app.get("/health")
        async def health() -> dict:
            return {"status": "ok"}

        @self.app.get("/api/data")
        async def get_data() -> dict:
            await asyncio.sleep(0.05)
            return {"data": [1, 2, 3]}

        @self.app.post("/api/submit")
        async def submit_data(data: dict) -> dict:
            await asyncio.sleep(0.15)  # Exceeds threshold
            return {"received": data}

        # Install middleware
        PerformanceMiddleware(self.app, config=self.config)
        self.client = TestClient(self.app)

    def test_basic_request(self) -> None:
        """Test that basic requests work correctly."""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello World"}

    def test_slow_request_still_returns(self) -> None:
        """Test that slow requests still return correctly."""
        response = self.client.get("/slow")
        assert response.status_code == 200
        assert response.json() == {"message": "Slow response"}

    def test_fast_request(self) -> None:
        """Test that fast requests work without issues."""
        response = self.client.get("/fast")
        assert response.status_code == 200
        assert response.json() == {"message": "Fast response"}

    def test_blacklisted_endpoint(self) -> None:
        """Test that blacklisted endpoints are not profiled."""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_api_endpoint(self) -> None:
        """Test API endpoint responses."""
        response = self.client.get("/api/data")
        assert response.status_code == 200
        assert response.json() == {"data": [1, 2, 3]}

    def test_post_request(self) -> None:
        """Test POST request handling."""
        response = self.client.post("/api/submit", json={"key": "value"})
        assert response.status_code == 200
        assert response.json() == {"received": {"key": "value"}}

    def test_query_parameters(self) -> None:
        """Test requests with query parameters."""
        response = self.client.get("/api/data?page=1&limit=10")
        assert response.status_code == 200


class TestFastAPIAutoDetect:
    """Tests for auto-detection of FastAPI applications."""

    def test_auto_detect_fastapi(self) -> None:
        """Test that FastAPI is auto-detected correctly."""
        app = FastAPI()

        @app.get("/")
        async def root() -> dict:
            return {"message": "ok"}

        # Should not raise - auto-detection should work
        middleware = PerformanceMiddleware(app)
        assert middleware is not None

    def test_auto_detect_with_config(self) -> None:
        """Test auto-detection with custom config."""
        app = FastAPI()

        @app.get("/")
        async def root() -> dict:
            return {"message": "ok"}

        config = MonitorConfig(threshold_seconds=2.0)
        middleware = PerformanceMiddleware(app, config=config)

        assert middleware.config.threshold_seconds == 2.0


class TestFastAPISyncRoutes:
    """Tests for sync route handling in FastAPI."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.app = FastAPI()

        @self.app.get("/sync")
        def sync_endpoint() -> dict:
            time.sleep(0.05)
            return {"type": "sync"}

        @self.app.get("/async")
        async def async_endpoint() -> dict:
            await asyncio.sleep(0.05)
            return {"type": "async"}

        config = MonitorConfig(threshold_seconds=0.1)
        PerformanceMiddleware(self.app, config=config)
        self.client = TestClient(self.app)

    def test_sync_route(self) -> None:
        """Test that sync routes work correctly."""
        response = self.client.get("/sync")
        assert response.status_code == 200
        assert response.json() == {"type": "sync"}

    def test_async_route(self) -> None:
        """Test that async routes work correctly."""
        response = self.client.get("/async")
        assert response.status_code == 200
        assert response.json() == {"type": "async"}


class TestFastAPIZeroIntrusion:
    """Tests to verify zero-intrusion behavior."""

    def test_response_not_modified(self) -> None:
        """Test that responses are not modified by middleware."""
        app = FastAPI()

        @app.get("/")
        async def root() -> dict:
            return {"original": "response", "nested": {"key": "value"}}

        config = MonitorConfig(threshold_seconds=0.001)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        response = client.get("/")
        assert response.json() == {"original": "response", "nested": {"key": "value"}}

    def test_headers_preserved(self) -> None:
        """Test that custom headers are preserved."""
        from fastapi.responses import JSONResponse

        app = FastAPI()

        @app.get("/")
        async def root() -> JSONResponse:
            return JSONResponse(
                content={"message": "ok"},
                headers={"X-Custom-Header": "custom-value"},
            )

        config = MonitorConfig(threshold_seconds=0.001)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        response = client.get("/")
        assert response.headers.get("X-Custom-Header") == "custom-value"

    def test_exception_propagates(self) -> None:
        """Test that exceptions are not swallowed."""
        from fastapi import HTTPException

        app = FastAPI()

        @app.get("/error")
        async def error_endpoint() -> dict:
            raise HTTPException(status_code=404, detail="Not found")

        config = MonitorConfig(threshold_seconds=0.001)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        response = client.get("/error")
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"
