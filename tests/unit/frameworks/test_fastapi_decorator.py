"""Unit tests for FastAPIProfileDecorator."""

import asyncio
import time

import pytest

pytest.importorskip("fastapi")

from web_perfmonitor.config import MonitorConfig
from web_perfmonitor.frameworks.fastapi import FastAPIProfileDecorator


class TestFastAPIProfileDecorator:
    """Tests for FastAPIProfileDecorator class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.config = MonitorConfig(threshold_seconds=0.1)

    def test_init(self) -> None:
        """Test decorator initialization."""
        decorator = FastAPIProfileDecorator(
            config=self.config,
            threshold=0.5,
            name="test_func",
        )

        assert decorator.config == self.config
        assert decorator.threshold == 0.5
        assert decorator.name == "test_func"

    def test_decorate_sync_function(self) -> None:
        """Test decorating a sync function."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        def sync_func() -> str:
            return "sync result"

        result = sync_func()
        assert result == "sync result"

    def test_decorate_async_function(self) -> None:
        """Test decorating an async function."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        async def async_func() -> str:
            await asyncio.sleep(0.01)
            return "async result"

        result = asyncio.run(async_func())
        assert result == "async result"

    def test_preserves_function_name(self) -> None:
        """Test that decorator preserves function name."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_preserves_async_function_name(self) -> None:
        """Test that decorator preserves async function name."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        async def my_async_function() -> None:
            pass

        assert my_async_function.__name__ == "my_async_function"

    def test_sync_function_with_exception(self) -> None:
        """Test that decorator re-raises exceptions from sync functions."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        def raising_func() -> None:
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            raising_func()

    def test_async_function_with_exception(self) -> None:
        """Test that decorator re-raises exceptions from async functions."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        async def async_raising_func() -> None:
            raise ValueError("async test error")

        with pytest.raises(ValueError, match="async test error"):
            asyncio.run(async_raising_func())

    def test_sync_function_passes_args(self) -> None:
        """Test that decorator passes arguments correctly for sync functions."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        def func_with_args(a: int, b: str, c: bool = True) -> tuple:
            return (a, b, c)

        result = func_with_args(1, "test", c=False)
        assert result == (1, "test", False)

    def test_async_function_passes_args(self) -> None:
        """Test that decorator passes arguments correctly for async functions."""
        decorator = FastAPIProfileDecorator(config=self.config)

        @decorator
        async def async_func_with_args(a: int, b: str, c: bool = True) -> tuple:
            return (a, b, c)

        result = asyncio.run(async_func_with_args(1, "test", c=False))
        assert result == (1, "test", False)


class TestFastAPIProfileDecoratorThreshold:
    """Tests for threshold behavior."""

    def test_custom_threshold_override(self) -> None:
        """Test that custom threshold overrides config."""
        config = MonitorConfig(threshold_seconds=1.0)
        decorator = FastAPIProfileDecorator(
            config=config,
            threshold=0.01,  # Much lower threshold
        )

        @decorator
        def slow_func() -> str:
            time.sleep(0.02)  # Sleep for 20ms
            return "done"

        # Should still work (profiling happens but doesn't affect result)
        result = slow_func()
        assert result == "done"
