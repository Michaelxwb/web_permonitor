"""Base decorator for function-level profiling.

This module defines the abstract base class for framework-specific
profile decorators.
"""

import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from ..config import MonitorConfig

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class BaseDecorator(ABC):
    """Abstract base class for profile decorators.

    Provides the common profiling logic with framework-specific
    context extraction delegated to subclasses.

    Attributes:
        config: The monitoring configuration.
        threshold: Custom threshold override (optional).
        name: Custom name override (optional).
    """

    def __init__(
        self,
        config: "MonitorConfig",
        threshold: Optional[float] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize the decorator.

        Args:
            config: The monitoring configuration.
            threshold: Optional custom threshold in seconds.
            name: Optional custom name for the profiled function.
        """
        self.config = config
        self.threshold = threshold
        self.name = name
        self._alert_manager: Any = None
        self._executor: Any = None

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

    def __call__(self, func: F) -> F:
        """Apply the decorator to a function.

        Args:
            func: The function to decorate.

        Returns:
            The decorated function with profiling enabled.
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ..profiler import Profiler

            # Get the effective threshold
            effective_threshold = self.threshold or self.config.threshold_seconds

            # Get the function name
            func_name = self.name or func.__name__

            profiler = Profiler()
            try:
                profiler.start()
                result = func(*args, **kwargs)
                return result
            except Exception:
                # Re-raise after stopping profiler
                raise
            finally:
                try:
                    profiler.stop()
                    duration = profiler.duration

                    # Only create profile if threshold exceeded
                    if duration > effective_threshold:
                        context = self._get_context()
                        profile = profiler.create_profile(
                            endpoint=func_name,
                            method="FUNCTION",
                            metadata=context,
                        )
                        self._process_profile(profile)
                except Exception as e:
                    # Never let profiling errors affect the function
                    logger.error(f"Error in profiler: {e}", exc_info=True)

        return wrapper  # type: ignore[return-value]

    def _process_profile(self, profile: Any) -> None:
        """Process a completed profile.

        Args:
            profile: The PerformanceProfile instance.
        """
        try:
            # Atomically check deduplication and record (prevents race conditions)
            if self.alert_manager.should_alert_and_record(profile.endpoint):
                # Submit notification (local report is always saved)
                self.executor.submit(profile)
                logger.debug(f"Submitted notification for function {profile.endpoint}")
            else:
                logger.debug(
                    f"Alert suppressed for {profile.endpoint} (within dedup window)"
                )
        except Exception as e:
            logger.error(f"Error processing profile: {e}", exc_info=True)

    @abstractmethod
    def _get_context(self) -> Dict[str, Any]:
        """Get framework-specific context information.

        Returns:
            Dictionary with context data (request info, etc.).
        """
        pass
