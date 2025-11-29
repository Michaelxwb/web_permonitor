"""Configuration management for web-perfmonitor.

This module provides the MonitorConfig dataclass for configuring
the performance monitoring system.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .exceptions import ConfigurationError


@dataclass
class MonitorConfig:
    """Global monitoring configuration.

    Controls all aspects of the performance monitoring system including
    thresholds, alert windows, URL filtering, and notification settings.

    Attributes:
        threshold_seconds: Performance threshold in seconds. Requests exceeding
            this duration will trigger alerts. Default: 1.0
        alert_window_days: Number of days to suppress duplicate alerts for the
            same endpoint. Default: 10
        max_performance_overhead: Maximum allowed performance overhead ratio.
            Must be between 0 and 1. Default: 0.05 (5%)
        log_path: Directory for logs and reports. Default: "/tmp"
        url_whitelist: List of URL patterns to monitor. If non-empty, only
            matching URLs are monitored and blacklist is ignored.
        url_blacklist: List of URL patterns to exclude from monitoring.
            Ignored if whitelist is non-empty.
        notice_list: List of notification channel configurations.
        notice_timeout_seconds: Timeout for each notification channel. Default: 30.0
        notice_queue_size: Maximum size of the notification task queue. Default: 1000
        graceful_shutdown_seconds: Time to wait for pending notifications on
            shutdown. Default: 5.0
        capture_request_headers: Whether to capture HTTP request headers in
            performance reports. Default: True
        included_headers: Optional list of specific headers to capture. If None,
            captures standard headers (X-Forwarded-For, X-Real-IP, X-Request-ID,
            X-Trace-ID, X-Correlation-ID, Referer, Content-Type, Accept,
            Accept-Language, Origin, User-Agent). Default: None
    """

    threshold_seconds: float = 1.0
    alert_window_days: int = 10
    max_performance_overhead: float = 0.05
    log_path: str = "/tmp"
    url_whitelist: List[str] = field(default_factory=list)
    url_blacklist: List[str] = field(default_factory=list)
    notice_list: List[Dict[str, Any]] = field(default_factory=list)
    notice_timeout_seconds: float = 30.0
    notice_queue_size: int = 1000
    graceful_shutdown_seconds: float = 5.0
    capture_request_headers: bool = True
    included_headers: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate all configuration values.

        Raises:
            ConfigurationError: If any configuration value is invalid.
        """
        if self.threshold_seconds <= 0:
            raise ConfigurationError(
                f"threshold_seconds must be positive, got {self.threshold_seconds}"
            )

        if self.alert_window_days < 0:
            raise ConfigurationError(
                f"alert_window_days must be non-negative, got {self.alert_window_days}"
            )

        if not 0 < self.max_performance_overhead <= 1:
            raise ConfigurationError(
                f"max_performance_overhead must be between 0 and 1, "
                f"got {self.max_performance_overhead}"
            )

        if self.notice_timeout_seconds <= 0:
            raise ConfigurationError(
                f"notice_timeout_seconds must be positive, got {self.notice_timeout_seconds}"
            )

        if self.notice_queue_size <= 0:
            raise ConfigurationError(
                f"notice_queue_size must be positive, got {self.notice_queue_size}"
            )

        if self.graceful_shutdown_seconds < 0:
            raise ConfigurationError(
                f"graceful_shutdown_seconds must be non-negative, "
                f"got {self.graceful_shutdown_seconds}"
            )

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        """Create configuration from environment variables.

        Environment variable mappings:
            PERF_THRESHOLD -> threshold_seconds
            PERF_ALERT_WINDOW -> alert_window_days
            PERF_MAX_OVERHEAD -> max_performance_overhead
            PERF_LOG_PATH -> log_path
            PERF_URL_WHITELIST -> url_whitelist (comma-separated)
            PERF_URL_BLACKLIST -> url_blacklist (comma-separated)
            PERF_NOTICE_TIMEOUT -> notice_timeout_seconds
            PERF_NOTICE_QUEUE_SIZE -> notice_queue_size
            PERF_SHUTDOWN_TIMEOUT -> graceful_shutdown_seconds
            PERF_CAPTURE_REQUEST_HEADERS -> capture_request_headers (true/false)
            PERF_INCLUDED_HEADERS -> included_headers (comma-separated)

        Returns:
            MonitorConfig instance with values from environment.

        Raises:
            ConfigurationError: If environment values are invalid.
        """
        kwargs: Dict[str, Any] = {}

        if threshold := os.environ.get("PERF_THRESHOLD"):
            try:
                kwargs["threshold_seconds"] = float(threshold)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_THRESHOLD value: {threshold}"
                ) from e

        if alert_window := os.environ.get("PERF_ALERT_WINDOW"):
            try:
                kwargs["alert_window_days"] = int(alert_window)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_ALERT_WINDOW value: {alert_window}"
                ) from e

        if max_overhead := os.environ.get("PERF_MAX_OVERHEAD"):
            try:
                kwargs["max_performance_overhead"] = float(max_overhead)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_MAX_OVERHEAD value: {max_overhead}"
                ) from e

        if log_path := os.environ.get("PERF_LOG_PATH"):
            kwargs["log_path"] = log_path

        if whitelist := os.environ.get("PERF_URL_WHITELIST"):
            kwargs["url_whitelist"] = [p.strip() for p in whitelist.split(",") if p.strip()]

        if blacklist := os.environ.get("PERF_URL_BLACKLIST"):
            kwargs["url_blacklist"] = [p.strip() for p in blacklist.split(",") if p.strip()]

        if notice_timeout := os.environ.get("PERF_NOTICE_TIMEOUT"):
            try:
                kwargs["notice_timeout_seconds"] = float(notice_timeout)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_NOTICE_TIMEOUT value: {notice_timeout}"
                ) from e

        if queue_size := os.environ.get("PERF_NOTICE_QUEUE_SIZE"):
            try:
                kwargs["notice_queue_size"] = int(queue_size)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_NOTICE_QUEUE_SIZE value: {queue_size}"
                ) from e

        if shutdown_timeout := os.environ.get("PERF_SHUTDOWN_TIMEOUT"):
            try:
                kwargs["graceful_shutdown_seconds"] = float(shutdown_timeout)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid PERF_SHUTDOWN_TIMEOUT value: {shutdown_timeout}"
                ) from e

        if capture_headers := os.environ.get("PERF_CAPTURE_REQUEST_HEADERS"):
            capture_headers_lower = capture_headers.lower()
            if capture_headers_lower in ("true", "1", "yes"):
                kwargs["capture_request_headers"] = True
            elif capture_headers_lower in ("false", "0", "no"):
                kwargs["capture_request_headers"] = False
            else:
                raise ConfigurationError(
                    f"Invalid PERF_CAPTURE_REQUEST_HEADERS value: {capture_headers}. "
                    "Must be true/false, 1/0, or yes/no"
                )

        if included_headers := os.environ.get("PERF_INCLUDED_HEADERS"):
            kwargs["included_headers"] = [h.strip() for h in included_headers.split(",") if h.strip()]

        return cls(**kwargs)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MonitorConfig":
        """Create configuration from a dictionary.

        Args:
            data: Configuration dictionary with field names as keys.

        Returns:
            MonitorConfig instance with values from dictionary.

        Raises:
            ConfigurationError: If dictionary values are invalid.
        """
        valid_fields = {
            "threshold_seconds",
            "alert_window_days",
            "max_performance_overhead",
            "log_path",
            "url_whitelist",
            "url_blacklist",
            "notice_list",
            "notice_timeout_seconds",
            "notice_queue_size",
            "graceful_shutdown_seconds",
            "capture_request_headers",
            "included_headers",
        }

        # Filter to only valid fields
        kwargs = {k: v for k, v in data.items() if k in valid_fields}

        try:
            return cls(**kwargs)
        except TypeError as e:
            raise ConfigurationError(f"Invalid configuration: {e}") from e

    def merge(self, **kwargs: Any) -> "MonitorConfig":
        """Create a new config with some values overridden.

        Args:
            **kwargs: Configuration values to override.

        Returns:
            New MonitorConfig instance with merged values.
        """
        current: Dict[str, Any] = {
            "threshold_seconds": self.threshold_seconds,
            "alert_window_days": self.alert_window_days,
            "max_performance_overhead": self.max_performance_overhead,
            "log_path": self.log_path,
            "url_whitelist": self.url_whitelist.copy(),
            "url_blacklist": self.url_blacklist.copy(),
            "notice_list": self.notice_list.copy(),
            "notice_timeout_seconds": self.notice_timeout_seconds,
            "notice_queue_size": self.notice_queue_size,
            "graceful_shutdown_seconds": self.graceful_shutdown_seconds,
            "capture_request_headers": self.capture_request_headers,
            "included_headers": self.included_headers.copy() if self.included_headers else None,
        }
        current.update(kwargs)
        return MonitorConfig(**current)


# Default configuration instance
_default_config: Optional[MonitorConfig] = None


def get_default_config() -> MonitorConfig:
    """Get the default global configuration.

    Returns:
        The default MonitorConfig instance.
    """
    global _default_config
    if _default_config is None:
        _default_config = MonitorConfig()
    return _default_config


def set_default_config(config: MonitorConfig) -> None:
    """Set the default global configuration.

    Args:
        config: The MonitorConfig to use as default.
    """
    global _default_config
    _default_config = config
