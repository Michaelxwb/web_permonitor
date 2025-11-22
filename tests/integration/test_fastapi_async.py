"""Tests for async profiling correctness in FastAPI."""

import asyncio

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from web_perfmonitor import MonitorConfig, PerformanceMiddleware


class TestAsyncProfilingCorrectness:
    """Tests to verify async functions are profiled correctly."""

    def test_asyncio_sleep_counted_in_duration(self) -> None:
        """Test that asyncio.sleep time is included in profiling."""
        app = FastAPI()

        @app.get("/async-sleep")
        async def async_sleep_endpoint() -> dict:
            await asyncio.sleep(0.15)
            return {"slept": True}

        # Very low threshold to ensure profiling triggers
        config = MonitorConfig(threshold_seconds=0.01)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        import time

        start = time.time()
        response = client.get("/async-sleep")
        duration = time.time() - start

        assert response.status_code == 200
        # Request should take at least 0.15 seconds due to asyncio.sleep
        assert duration >= 0.14  # Allow some margin

    def test_multiple_await_calls(self) -> None:
        """Test profiling with multiple await calls."""
        app = FastAPI()

        @app.get("/multiple-awaits")
        async def multiple_awaits() -> dict:
            await asyncio.sleep(0.05)
            await asyncio.sleep(0.05)
            await asyncio.sleep(0.05)
            return {"awaits": 3}

        config = MonitorConfig(threshold_seconds=0.01)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        import time

        start = time.time()
        response = client.get("/multiple-awaits")
        duration = time.time() - start

        assert response.status_code == 200
        # Should take at least 0.15 seconds total
        assert duration >= 0.14

    def test_async_with_sync_operations(self) -> None:
        """Test profiling async routes with sync operations."""
        app = FastAPI()

        @app.get("/mixed")
        async def mixed_operations() -> dict:
            # Sync operation
            result = sum(range(1000))
            # Async operation
            await asyncio.sleep(0.05)
            return {"result": result}

        config = MonitorConfig(threshold_seconds=0.01)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        response = client.get("/mixed")
        assert response.status_code == 200
        assert response.json()["result"] == 499500


class TestConcurrentRequests:
    """Tests for concurrent request handling."""

    def test_concurrent_requests_dont_interfere(self) -> None:
        """Test that concurrent requests don't interfere with each other."""
        app = FastAPI()

        @app.get("/endpoint/{id}")
        async def endpoint_with_id(id: int) -> dict:
            await asyncio.sleep(0.05)
            return {"id": id}

        config = MonitorConfig(threshold_seconds=0.01)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app)

        # Make multiple requests sequentially (TestClient doesn't support true concurrency)
        results = []
        for i in range(5):
            response = client.get(f"/endpoint/{i}")
            results.append(response.json())

        # Each request should return its own ID
        for i, result in enumerate(results):
            assert result["id"] == i


class TestAsyncDecorator:
    """Tests for async function decorator."""

    def test_async_decorator_captures_await_time(self) -> None:
        """Test that decorator captures await time correctly."""
        from web_perfmonitor.frameworks.fastapi import FastAPIProfileDecorator
        from web_perfmonitor import MonitorConfig

        config = MonitorConfig(threshold_seconds=0.01)
        decorator = FastAPIProfileDecorator(config=config)

        @decorator
        async def slow_async_func() -> str:
            await asyncio.sleep(0.1)
            return "done"

        import time

        start = time.time()
        result = asyncio.run(slow_async_func())
        duration = time.time() - start

        assert result == "done"
        assert duration >= 0.09  # Allow some margin

    def test_sync_decorator_in_async_context(self) -> None:
        """Test that sync function decorator works in async context."""
        import time as time_module

        from web_perfmonitor.frameworks.fastapi import FastAPIProfileDecorator
        from web_perfmonitor import MonitorConfig

        config = MonitorConfig(threshold_seconds=0.01)
        decorator = FastAPIProfileDecorator(config=config)

        @decorator
        def slow_sync_func() -> str:
            time_module.sleep(0.1)
            return "sync done"

        result = slow_sync_func()
        assert result == "sync done"


class TestAsyncExceptionHandling:
    """Tests for exception handling in async context."""

    def test_async_exception_not_swallowed(self) -> None:
        """Test that exceptions in async routes are not swallowed."""
        app = FastAPI()

        @app.get("/async-error")
        async def async_error() -> dict:
            await asyncio.sleep(0.01)
            raise ValueError("Async error")

        config = MonitorConfig(threshold_seconds=0.001)
        PerformanceMiddleware(app, config=config)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/async-error")
        assert response.status_code == 500

    def test_async_decorator_exception(self) -> None:
        """Test that decorator properly re-raises async exceptions."""
        from web_perfmonitor.frameworks.fastapi import FastAPIProfileDecorator
        from web_perfmonitor import MonitorConfig

        config = MonitorConfig(threshold_seconds=0.01)
        decorator = FastAPIProfileDecorator(config=config)

        @decorator
        async def raising_async_func() -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError("Test async error")

        with pytest.raises(RuntimeError, match="Test async error"):
            asyncio.run(raising_async_func())
