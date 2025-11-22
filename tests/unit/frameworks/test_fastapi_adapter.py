"""Unit tests for FastAPIAdapter."""

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI
from flask import Flask

from web_perfmonitor.config import MonitorConfig
from web_perfmonitor.core import FrameworkRegistry
from web_perfmonitor.frameworks.fastapi import FastAPIAdapter


class TestFastAPIAdapter:
    """Tests for FastAPIAdapter class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.adapter = FastAPIAdapter()
        self.config = MonitorConfig(threshold_seconds=0.5)

    def test_can_handle_fastapi_app(self) -> None:
        """Test that adapter can handle FastAPI applications."""
        app = FastAPI()
        assert self.adapter.can_handle(app) is True

    def test_cannot_handle_flask_app(self) -> None:
        """Test that adapter cannot handle Flask applications."""
        app = Flask(__name__)
        assert self.adapter.can_handle(app) is False

    def test_cannot_handle_other_objects(self) -> None:
        """Test that adapter cannot handle non-app objects."""
        assert self.adapter.can_handle({}) is False
        assert self.adapter.can_handle("string") is False
        assert self.adapter.can_handle(None) is False

    def test_get_framework_name(self) -> None:
        """Test framework name is 'fastapi'."""
        assert self.adapter.get_framework_name() == "fastapi"

    def test_registered_in_framework_registry(self) -> None:
        """Test that adapter is registered in FrameworkRegistry."""
        assert FrameworkRegistry.is_registered("fastapi")
        adapter_cls = FrameworkRegistry.get("fastapi")
        assert adapter_cls == FastAPIAdapter

    def test_create_middleware(self) -> None:
        """Test middleware creation."""
        app = FastAPI()
        middleware = self.adapter.create_middleware(app, self.config)

        from web_perfmonitor.frameworks.fastapi import FastAPIMiddleware
        assert isinstance(middleware, FastAPIMiddleware)

    def test_create_decorator(self) -> None:
        """Test decorator factory creation."""
        decorator_factory = self.adapter.create_decorator(self.config)
        assert callable(decorator_factory)

        # Test creating a decorator instance
        decorator = decorator_factory(threshold=0.1, name="test_func")
        assert decorator is not None


class TestFastAPIAdapterAutoDetect:
    """Tests for auto-detection functionality."""

    def test_auto_detect_fastapi(self) -> None:
        """Test that FastAPI app is auto-detected."""
        # Import frameworks to trigger registration
        from web_perfmonitor import frameworks  # noqa: F401

        app = FastAPI()
        adapter = FrameworkRegistry.auto_detect(app)

        assert adapter is not None
        assert adapter.get_framework_name() == "fastapi"
