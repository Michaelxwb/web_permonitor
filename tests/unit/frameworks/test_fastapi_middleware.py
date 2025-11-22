"""Unit tests for FastAPIMiddleware."""

import pytest

pytest.importorskip("fastapi")

from web_perfmonitor.config import MonitorConfig
from web_perfmonitor.frameworks.fastapi import FastAPIMiddleware


class TestFastAPIMiddleware:
    """Tests for FastAPIMiddleware class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = MonitorConfig(
            threshold_seconds=0.5,
            url_whitelist=[],
            url_blacklist=["/health", "/metrics"],
        )
        self.middleware = FastAPIMiddleware(self.config)

    def test_init(self) -> None:
        """Test middleware initialization."""
        assert self.middleware.config == self.config
        assert self.middleware._app is None

    def test_should_profile_returns_true_for_allowed_paths(self) -> None:
        """Test that should_profile returns True for allowed paths."""
        assert self.middleware.should_profile("/api/users") is True
        assert self.middleware.should_profile("/api/data") is True

    def test_should_profile_returns_false_for_blacklisted_paths(self) -> None:
        """Test that should_profile returns False for blacklisted paths."""
        assert self.middleware.should_profile("/health") is False
        assert self.middleware.should_profile("/metrics") is False

    def test_should_profile_with_whitelist(self) -> None:
        """Test should_profile with whitelist configuration."""
        config = MonitorConfig(
            threshold_seconds=0.5,
            url_whitelist=["/api/*"],
            url_blacklist=[],
        )
        middleware = FastAPIMiddleware(config)

        assert middleware.should_profile("/api/users") is True
        assert middleware.should_profile("/other/path") is False


class TestFastAPIMiddlewareBuildEndpointKey:
    """Tests for endpoint key building."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = MonitorConfig(threshold_seconds=0.5)
        self.middleware = FastAPIMiddleware(self.config)

    def test_build_endpoint_key_simple_path(self) -> None:
        """Test endpoint key for simple path."""
        from starlette.requests import Request
        from starlette.testclient import TestClient

        # Create a mock request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "query_string": b"",
            "headers": [],
        }
        request = Request(scope)

        key = self.middleware._build_endpoint_key(request)
        assert key == "GET /api/users"

    def test_build_endpoint_key_with_query_string(self) -> None:
        """Test endpoint key with query string."""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/search",
            "query_string": b"q=test&page=1",
            "headers": [],
        }
        request = Request(scope)

        key = self.middleware._build_endpoint_key(request)
        assert key == "POST /api/search?q=test&page=1"


class TestFastAPIMiddlewareMetadata:
    """Tests for request metadata extraction."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = MonitorConfig(threshold_seconds=0.5)
        self.middleware = FastAPIMiddleware(self.config)

    def test_get_request_metadata_basic(self) -> None:
        """Test basic metadata extraction."""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/users",
            "query_string": b"",
            "headers": [
                (b"user-agent", b"Mozilla/5.0"),
                (b"content-length", b"100"),
            ],
            "client": ("127.0.0.1", 8000),
        }
        request = Request(scope)

        metadata = self.middleware._get_request_metadata(request)

        assert metadata["path"] == "/api/users"
        assert metadata["method"] == "GET"
        assert metadata["remote_addr"] == "127.0.0.1"
        assert metadata["user_agent"] == "Mozilla/5.0"
        assert metadata["content_length"] == 100

    def test_get_request_metadata_with_query_params(self) -> None:
        """Test metadata extraction with query parameters."""
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/search",
            "query_string": b"q=test&page=1",
            "headers": [],
        }
        request = Request(scope)

        metadata = self.middleware._get_request_metadata(request)

        assert metadata["query_string"] == "q=test&page=1"
        assert metadata["query_params"]["q"] == "test"
        assert metadata["query_params"]["page"] == "1"
