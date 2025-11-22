"""Web Performance Monitor - A performance monitoring library for Python web frameworks.

This package provides automatic performance monitoring and alerting for web
applications. Currently supports Flask, with extensibility for other frameworks.

Quick Start:
    from flask import Flask
    from web_perfmonitor import PerformanceMiddleware

    app = Flask(__name__)
    PerformanceMiddleware(app)  # That's it!

Full Configuration:
    from web_perfmonitor import PerformanceMiddleware, MonitorConfig

    config = MonitorConfig(
        threshold_seconds=0.5,
        notice_list=[
            {"type": "local", "format": "markdown"},
            {
                "type": "mattermost",
                "server_url": "https://mm.example.com",
                "token": "xxx",
                "channel_id": "yyy"
            }
        ]
    )
    PerformanceMiddleware(app, config=config)

Function-Level Profiling:
    from web_perfmonitor import profile

    @profile()
    def slow_function():
        ...

    @profile(threshold=0.1, name="critical_op")
    def another_function():
        ...
"""

__version__ = "0.1.0"

import logging
from typing import Any, Callable, Optional, TYPE_CHECKING

from .config import MonitorConfig
from .exceptions import (
    ConfigurationError,
    NotificationError,
    ProfilerError,
    WebPerfMonitorError,
)
from .models import PerformanceProfile

if TYPE_CHECKING:
    from .core import BaseMiddleware

logger = logging.getLogger(__name__)

# Module-level config for decorator
_global_config: Optional[MonitorConfig] = None


class PerformanceMiddleware:
    """Performance monitoring middleware for web applications.

    Automatically detects the web framework and installs the appropriate
    middleware for request-level performance monitoring.

    Attributes:
        config: The monitoring configuration.
        middleware: The framework-specific middleware instance.

    Example:
        # Minimal setup
        from flask import Flask
        from web_perfmonitor import PerformanceMiddleware

        app = Flask(__name__)
        PerformanceMiddleware(app)

        # With configuration
        from web_perfmonitor import PerformanceMiddleware, MonitorConfig

        config = MonitorConfig(threshold_seconds=0.5)
        PerformanceMiddleware(app, config=config)

        # With quick config kwargs
        PerformanceMiddleware(app, threshold_seconds=0.5)
    """

    def __init__(
        self,
        app: Any,
        config: Optional[MonitorConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the performance middleware.

        Args:
            app: The web application instance (e.g., Flask app).
            config: Optional monitoring configuration. If None, uses
                defaults or environment variables.
            **kwargs: Quick configuration parameters that override
                config values (e.g., threshold_seconds=0.5).

        Raises:
            ConfigurationError: If the framework cannot be detected or
                configuration is invalid.
        """
        global _global_config

        # Build configuration
        if config is None:
            config = MonitorConfig()

        # Apply kwargs overrides
        if kwargs:
            config = config.merge(kwargs)

        self.config = config
        _global_config = config

        # Auto-discover frameworks
        from . import frameworks  # noqa: F401
        from .core import FrameworkRegistry

        # Auto-detect framework
        adapter = FrameworkRegistry.auto_detect(app)
        if adapter is None:
            raise ConfigurationError(
                f"Could not detect framework for application type: {type(app).__name__}. "
                f"Supported frameworks: {FrameworkRegistry.list_frameworks()}"
            )

        # Create and install middleware
        self._middleware: "BaseMiddleware" = adapter.create_middleware(app, config)
        logger.info(
            f"PerformanceMiddleware installed for {adapter.get_framework_name()} app"
        )

    @property
    def middleware(self) -> "BaseMiddleware":
        """Get the underlying framework-specific middleware.

        Returns:
            The middleware instance.
        """
        return self._middleware

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Gracefully shutdown the middleware.

        Waits for pending notifications to complete.

        Args:
            timeout: Optional timeout in seconds. Uses config value if None.
        """
        self._middleware.shutdown(timeout)
        logger.info("PerformanceMiddleware shutdown complete")


def profile(
    threshold: Optional[float] = None,
    name: Optional[str] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for function-level performance profiling.

    Profiles the decorated function and generates performance reports
    when execution time exceeds the threshold.

    Args:
        threshold: Custom threshold in seconds. Uses global config if None.
        name: Custom name for the profiled function. Uses function name if None.

    Returns:
        Decorator function that wraps the target function with profiling.

    Example:
        @profile()
        def slow_function():
            ...

        @profile(threshold=0.1, name="critical_operation")
        def another_function():
            ...
    """
    from . import frameworks  # noqa: F401
    from .core import FrameworkRegistry

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Get config
        config = _global_config or MonitorConfig()

        # Try to get framework-specific decorator
        for framework_name in FrameworkRegistry.list_frameworks():
            try:
                adapter = FrameworkRegistry.get_instance(framework_name)
                decorator_factory = adapter.create_decorator(config)
                return decorator_factory(threshold=threshold, name=name)(func)
            except Exception:
                continue

        # Fallback to generic profiling
        from functools import wraps

        from .profiler import Profiler

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            effective_threshold = threshold or config.threshold_seconds
            func_name = name or func.__name__

            profiler = Profiler()
            try:
                profiler.start()
                result = func(*args, **kwargs)
                return result
            except Exception:
                raise
            finally:
                try:
                    profiler.stop()
                    duration = profiler.duration
                    if duration > effective_threshold:
                        _profile = profiler.create_profile(
                            endpoint=func_name,
                            method="FUNCTION",
                        )
                        logger.warning(
                            f"Function {func_name} exceeded threshold: "
                            f"{duration:.3f}s > {effective_threshold}s"
                        )
                except Exception as e:
                    logger.error(f"Error in profiler: {e}", exc_info=True)

        return wrapper

    return decorator


def get_config() -> Optional[MonitorConfig]:
    """Get the global configuration.

    Returns:
        The global MonitorConfig instance, or None if not initialized.
    """
    return _global_config


def set_config(config: MonitorConfig) -> None:
    """Set the global configuration.

    Args:
        config: The MonitorConfig instance to use globally.
    """
    global _global_config
    _global_config = config


__all__ = [
    # Version
    "__version__",
    # Core components
    "PerformanceMiddleware",
    "profile",
    # Configuration
    "MonitorConfig",
    "get_config",
    "set_config",
    # Types
    "PerformanceProfile",
    # Exceptions
    "WebPerfMonitorError",
    "ConfigurationError",
    "NotificationError",
    "ProfilerError",
]
