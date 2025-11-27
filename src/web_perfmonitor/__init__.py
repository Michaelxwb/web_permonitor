"""Web Performance Monitor - A performance monitoring library for Python web frameworks.

This package provides automatic performance monitoring and alerting for web
applications. Supports Flask and FastAPI, with extensibility for other frameworks.

Quick Start (Flask):
    from flask import Flask
    from web_perfmonitor import PerformanceMiddleware

    app = Flask(__name__)
    PerformanceMiddleware(app)  # That's it!

Quick Start (FastAPI):
    from fastapi import FastAPI
    from web_perfmonitor import PerformanceMiddleware

    app = FastAPI()
    PerformanceMiddleware(app)  # Auto-detects FastAPI

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
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
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

# Track if file logging has been set up
_file_handler_initialized = False

# Module-level config for decorator
_global_config: Optional[MonitorConfig] = None


def _setup_file_logging(log_path: str, log_level: int = logging.INFO) -> None:
    """Set up file logging for the web_perfmonitor package.

    Creates a rotating log file in the specified directory.

    Args:
        log_path: Directory path for log files.
        log_level: Logging level (default: INFO).
    """
    global _file_handler_initialized

    if _file_handler_initialized:
        return

    try:
        # Ensure directory exists
        log_dir = Path(log_path)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file path
        log_file = log_dir / "perfmonitor.log"

        # Create rotating file handler (10MB max, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )

        # Set format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)

        # Add handler to web_perfmonitor logger and all sub-loggers
        root_logger = logging.getLogger("web_perfmonitor")
        root_logger.addHandler(file_handler)

        # Ensure the logger level allows the messages through
        if root_logger.level == logging.NOTSET or root_logger.level > log_level:
            root_logger.setLevel(log_level)

        _file_handler_initialized = True
        logger.info(f"File logging initialized: {log_file}")

    except Exception as e:
        logger.warning(f"Failed to set up file logging: {e}")


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

        # Set up file logging in log_path directory
        _setup_file_logging(config.log_path)

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

        # Log startup information with configuration details
        logger.info(
            f"PerformanceMiddleware installed for {adapter.get_framework_name()} app"
        )
        logger.info(
            f"Performance monitoring enabled - "
            f"threshold: {config.threshold_seconds}s, "
            f"log_path: {config.log_path}, "
            f"alert_window: {config.alert_window_days} days"
        )
        if config.url_whitelist:
            logger.info(f"URL whitelist: {config.url_whitelist}")
        if config.url_blacklist:
            logger.info(f"URL blacklist: {config.url_blacklist}")
        if config.notice_list:
            notifier_types = [n.get("type", "unknown") for n in config.notice_list]
            logger.info(f"Notifiers configured: {notifier_types}")

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
                except ProfilerError as e:
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
