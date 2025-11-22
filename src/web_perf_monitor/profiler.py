"""Profiler wrapper for pyinstrument integration.

This module provides a wrapper around pyinstrument's Profiler class
with additional convenience methods for the web-perfmonitor system.
"""

import logging
from typing import Optional

from pyinstrument import Profiler as PyInstrumentProfiler

from .exceptions import ProfilerError
from .models import PerformanceProfile

logger = logging.getLogger(__name__)


class Profiler:
    """Wrapper around pyinstrument.Profiler.

    Provides a simplified interface for profiling code blocks and
    generating performance reports.

    Example:
        profiler = Profiler()
        profiler.start()
        # ... code to profile ...
        profiler.stop()
        profile = profiler.create_profile("/api/users", "GET")
    """

    def __init__(self) -> None:
        """Initialize the profiler."""
        self._profiler: Optional[PyInstrumentProfiler] = None
        self._duration: Optional[float] = None

    def start(self) -> None:
        """Start profiling.

        Creates a new pyinstrument profiler and begins sampling.

        Raises:
            ProfilerError: If profiler is already running.
        """
        if self._profiler is not None:
            raise ProfilerError("Profiler is already running")

        try:
            self._profiler = PyInstrumentProfiler()
            self._profiler.start()
        except Exception as e:
            self._profiler = None
            raise ProfilerError(f"Failed to start profiler: {e}", cause=e)

    def stop(self) -> None:
        """Stop profiling.

        Stops the profiler and records the duration.

        Raises:
            ProfilerError: If profiler is not running.
        """
        if self._profiler is None:
            raise ProfilerError("Profiler is not running")

        try:
            self._profiler.stop()
            # Get duration from the profiler's last session
            if self._profiler.last_session:
                self._duration = self._profiler.last_session.duration
            else:
                self._duration = 0.0
        except Exception as e:
            raise ProfilerError(f"Failed to stop profiler: {e}", cause=e)

    @property
    def duration(self) -> float:
        """Get the profiled duration in seconds.

        Returns:
            Duration in seconds.

        Raises:
            ProfilerError: If profiler hasn't been stopped yet.
        """
        if self._duration is None:
            raise ProfilerError("Profiler has not been stopped yet")
        return self._duration

    @property
    def is_running(self) -> bool:
        """Check if the profiler is currently running.

        Returns:
            True if profiler is running, False otherwise.
        """
        return self._profiler is not None and self._profiler.is_running

    def get_html_report(self) -> str:
        """Get the HTML format profiling report.

        Returns:
            HTML string with the profiling report.

        Raises:
            ProfilerError: If profiler hasn't been stopped yet.
        """
        if self._profiler is None:
            raise ProfilerError("Profiler has not been run")

        try:
            return self._profiler.output_html()
        except Exception as e:
            raise ProfilerError(f"Failed to generate HTML report: {e}", cause=e)

    def get_text_report(self) -> str:
        """Get the text format profiling report.

        Returns:
            Text string with the profiling report.

        Raises:
            ProfilerError: If profiler hasn't been stopped yet.
        """
        if self._profiler is None:
            raise ProfilerError("Profiler has not been run")

        try:
            return self._profiler.output_text()
        except Exception as e:
            raise ProfilerError(f"Failed to generate text report: {e}", cause=e)

    def create_profile(
        self,
        endpoint: str,
        method: str,
        metadata: Optional[dict] = None,
    ) -> PerformanceProfile:
        """Create a PerformanceProfile from the profiling results.

        Args:
            endpoint: The endpoint path or function name.
            method: HTTP method or "FUNCTION".
            metadata: Optional additional context.

        Returns:
            A new PerformanceProfile instance.

        Raises:
            ProfilerError: If profiler hasn't completed.
        """
        if self._profiler is None or self._duration is None:
            raise ProfilerError("Profiler has not completed")

        try:
            html_report = self.get_html_report()
            text_report = self.get_text_report()

            return PerformanceProfile.create(
                endpoint=endpoint,
                method=method,
                duration_seconds=self._duration,
                html_report=html_report,
                text_report=text_report,
                metadata=metadata,
            )
        except ProfilerError:
            raise
        except Exception as e:
            raise ProfilerError(f"Failed to create profile: {e}", cause=e)

    def reset(self) -> None:
        """Reset the profiler for reuse.

        Clears the internal profiler state so this instance can be used again.
        """
        self._profiler = None
        self._duration = None
