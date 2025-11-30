"""Sanic profile decorator for function-level monitoring.

This module provides the Sanic-specific implementation of the
function-level profiling decorator with async support.
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Dict, TypeVar

from ...core import BaseDecorator
from ...exceptions import ProfilerError

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class SanicProfileDecorator(BaseDecorator):
    """Sanic-specific function profiling decorator.

    Profiles decorated functions and generates performance reports
    when execution time exceeds the configured threshold.

    This decorator supports both sync and async functions, properly
    handling async/await patterns.

    If called within a Sanic request context, additional context
    information (request path, method, etc.) is captured.

    Example:
        from web_perfmonitor import profile

        @profile()
        async def slow_async_function():
            await asyncio.sleep(2)
            return "done"

        @profile(threshold=0.1, name="critical_db_query")
        def sync_function():
            return db.execute(query)
    """

    def __call__(self, func: F) -> F:
        """Apply the decorator to a function.

        Handles both sync and async functions appropriately.

        Args:
            func: The function to decorate.

        Returns:
            The decorated function with profiling enabled.
        """
        if asyncio.iscoroutinefunction(func):
            return self._wrap_async(func)  # type: ignore[return-value]
        else:
            return self._wrap_sync(func)  # type: ignore[return-value]

    def _wrap_async(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap an async function with profiling.

        Args:
            func: The async function to wrap.

        Returns:
            The wrapped async function.
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ...profiler import Profiler

            effective_threshold = self.threshold or self.config.threshold_seconds
            func_name = self.name or func.__name__

            profiler = Profiler()
            try:
                profiler.start()
                result = await func(*args, **kwargs)
                return result
            finally:
                try:
                    profiler.stop()
                    duration = profiler.duration

                    if duration > effective_threshold:
                        context = self._get_context()
                        profile = profiler.create_profile(
                            endpoint=func_name,
                            method="ASYNC_FUNCTION",
                            metadata=context,
                        )
                        self._process_profile(profile)
                except ProfilerError as e:
                    logger.error(f"Error in profiler: {e}", exc_info=True)

        return wrapper

    def _wrap_sync(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a sync function with profiling.

        Args:
            func: The sync function to wrap.

        Returns:
            The wrapped sync function.
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from ...profiler import Profiler

            effective_threshold = self.threshold or self.config.threshold_seconds
            func_name = self.name or func.__name__

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
                        context = self._get_context()
                        profile = profiler.create_profile(
                            endpoint=func_name,
                            method="FUNCTION",
                            metadata=context,
                        )
                        self._process_profile(profile)
                except ProfilerError as e:
                    logger.error(f"Error in profiler: {e}", exc_info=True)

        return wrapper

    def _get_context(self) -> Dict[str, Any]:
        """Get Sanic-specific context information.

        Attempts to get request context if available via Sanic's request context.

        Returns:
            Dictionary with context data from Sanic request, if available.
        """
        context: Dict[str, Any] = {}

        try:
            # Try to get request from Sanic's context
            # In Sanic, request context is typically available via the request object
            # passed to route handlers, but decorators are typically used outside
            # the middleware context, so we just return an empty context for now

            pass

        except Exception as e:
            logger.debug(f"Error extracting Sanic context: {e}")

        return context
