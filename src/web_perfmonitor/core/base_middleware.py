"""Base middleware for performance monitoring.

This module defines the abstract base class for framework-specific
middleware implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import MonitorConfig
    from ..models import PerformanceProfile

logger = logging.getLogger(__name__)


class BaseMiddleware(ABC):
    """Abstract base class for framework middleware.

    Provides common functionality for URL filtering, alert deduplication,
    and notification dispatching. Framework-specific implementations only
    need to implement the installation and request hooks.

    Attributes:
        config: The monitoring configuration.
        _url_filter: URL filter instance (lazy loaded).
        _alert_manager: Alert manager instance (lazy loaded).
        _executor: Notification executor instance (lazy loaded).
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the middleware.

        Args:
            config: The monitoring configuration.
        """
        self.config = config
        self._url_filter: Any = None
        self._alert_manager: Any = None
        self._executor: Any = None

    @property
    def url_filter(self) -> Any:
        """Get the URL filter (lazy loaded).

        Returns:
            The UrlFilter instance.
        """
        if self._url_filter is None:
            from ..filter import UrlFilter

            self._url_filter = UrlFilter(
                self.config.url_whitelist, self.config.url_blacklist
            )
        return self._url_filter

    @property
    def alert_manager(self) -> Any:
        """Get the alert manager (lazy loaded).

        Returns:
            The AlertManager instance.
        """
        if self._alert_manager is None:
            from ..alert import AlertManager

            self._alert_manager = AlertManager(self.config)
        return self._alert_manager

    @property
    def executor(self) -> Any:
        """Get the notification executor (lazy loaded).

        Returns:
            The NotificationExecutor instance.
        """
        if self._executor is None:
            from ..executor import NotificationExecutor

            self._executor = NotificationExecutor(self.config)
        return self._executor

    def should_profile(self, path: str) -> bool:
        """Determine if a path should be profiled.

        Uses the URL filter to check whitelist/blacklist rules.

        Args:
            path: The request path to check.

        Returns:
            True if the path should be profiled, False otherwise.
        """
        return self.url_filter.should_monitor(path)

    def process_profile(self, profile: "PerformanceProfile") -> None:
        """Process a completed profile.

        Checks alert deduplication and submits notifications if needed.

        Args:
            profile: The completed performance profile.
        """
        try:
            # Atomically check if we should send an alert and record it (prevents race conditions)
            if self.alert_manager.should_alert_and_record(profile.endpoint):
                # Submit notification task (local report is always saved)
                self.executor.submit(profile)
                logger.debug(f"Submitted notification for {profile.endpoint}")
            else:
                logger.debug(
                    f"Alert suppressed for {profile.endpoint} (within dedup window)"
                )
        except Exception as e:
            # Never let notification errors affect the application
            logger.error(f"Error processing profile: {e}", exc_info=True)

    @abstractmethod
    def install(self, app: Any) -> None:
        """Install the middleware into the application.

        Args:
            app: The framework application instance.
        """
        pass

    @abstractmethod
    def _before_request(self) -> None:
        """Hook called before request processing.

        Should start the profiler if the request should be profiled.
        """
        pass

    @abstractmethod
    def _after_request(self, response: Any) -> Any:
        """Hook called after request processing.

        Should stop the profiler, check thresholds, and process
        the profile if needed.

        Args:
            response: The framework response object.

        Returns:
            The response object (unmodified).
        """
        pass

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Shutdown the middleware.

        Waits for pending notifications to complete.

        Args:
            timeout: Optional timeout in seconds. Uses config value if None.
        """
        if self._executor is not None:
            actual_timeout = timeout or self.config.graceful_shutdown_seconds
            self._executor.shutdown(actual_timeout)
