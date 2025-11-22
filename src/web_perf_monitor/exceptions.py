"""Web Performance Monitor exceptions.

This module defines all custom exceptions used throughout the web-perf-monitor package.
"""

from typing import Optional


class WebPerfMonitorError(Exception):
    """Base exception for all web-perf-monitor errors.

    All custom exceptions in this package inherit from this class,
    allowing users to catch all package-specific errors with a single except clause.
    """

    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error description.
            cause: Optional underlying exception that caused this error.
        """
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:
        if self.cause:
            return f"{self.message} (caused by: {self.cause})"
        return self.message


class ConfigurationError(WebPerfMonitorError):
    """Raised when there is a configuration error.

    This includes invalid configuration values, missing required fields,
    or configuration validation failures.
    """

    pass


class NotificationError(WebPerfMonitorError):
    """Raised when a notification fails to send.

    This includes network errors, authentication failures,
    or any other issues with notification delivery.
    """

    pass


class ProfilerError(WebPerfMonitorError):
    """Raised when there is an error during performance profiling.

    This includes pyinstrument initialization failures,
    sampling errors, or report generation issues.
    """

    pass
