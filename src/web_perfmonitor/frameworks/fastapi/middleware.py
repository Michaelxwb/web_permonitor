"""FastAPI middleware for performance monitoring.

This module provides the FastAPI-specific middleware implementation
for automatic request profiling with async support.

Uses pure ASGI middleware instead of BaseHTTPMiddleware to ensure
pyinstrument can correctly capture the full async call stack.
"""

import logging
from contextvars import ContextVar
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ...core import BaseMiddleware

if TYPE_CHECKING:
    from fastapi import FastAPI

    from ...config import MonitorConfig
    from ...profiler import Profiler

logger = logging.getLogger(__name__)

# Context variable for storing profiler instance per request
_profiler_var: ContextVar[Optional["Profiler"]] = ContextVar("profiler", default=None)


class FastAPIMiddleware(BaseMiddleware):
    """FastAPI middleware for automatic request profiling.

    Hooks into FastAPI/Starlette's request lifecycle to automatically profile
    all requests (or filtered subset) and generate performance reports
    when thresholds are exceeded.

    Uses pure ASGI middleware to ensure pyinstrument can capture the
    complete async call stack, including all awaited functions.

    Attributes:
        config: The monitoring configuration.
        _app: The FastAPI application instance (set after install).

    Example:
        from fastapi import FastAPI
        from web_perfmonitor import MonitorConfig
        from web_perfmonitor.frameworks.fastapi import FastAPIMiddleware

        app = FastAPI()
        config = MonitorConfig(threshold_seconds=0.5)
        middleware = FastAPIMiddleware(config)
        middleware.install(app)
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the FastAPI middleware.

        Args:
            config: The monitoring configuration.
        """
        super().__init__(config)
        self._app: Optional["FastAPI"] = None

    def install(self, app: "FastAPI") -> None:
        """Install the middleware into a FastAPI application.

        Uses pure ASGI middleware to wrap the application, ensuring
        pyinstrument can trace the full async call stack.

        Args:
            app: The FastAPI application instance.
        """
        self._app = app

        # Store reference to self for the middleware class
        parent = self

        # Create a middleware class that captures our parent reference
        class ProfilerMiddleware:
            """ASGI middleware that wraps the app for profiling."""

            def __init__(self, app: ASGIApp) -> None:
                # Note: add_middleware passes app as keyword argument
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                # Create request object for path checking
                request = Request(scope)
                path = request.url.path

                # Check if this path should be profiled
                if not parent.should_profile(path):
                    await self.app(scope, receive, send)
                    return

                # Start profiling
                profiler: Optional["Profiler"] = None
                try:
                    from ...profiler import Profiler

                    profiler = Profiler()
                    profiler.start()
                    _profiler_var.set(profiler)
                    logger.debug(f"Started profiling: {request.method} {path}")
                except Exception as e:
                    logger.error(f"Error starting profiler: {e}", exc_info=True)
                    await self.app(scope, receive, send)
                    return

                # Track response status
                status_code = 200

                async def send_wrapper(message: Message) -> None:
                    nonlocal status_code
                    if message["type"] == "http.response.start":
                        status_code = message.get("status", 200)
                    await send(message)

                try:
                    # Process the request - this runs in the same async context
                    await self.app(scope, receive, send_wrapper)
                finally:
                    # Stop profiler and process results
                    try:
                        if profiler is not None:
                            profiler.stop()
                            duration = profiler.duration

                            if duration > parent.config.threshold_seconds:
                                endpoint_key = parent._build_endpoint_key(request)
                                profile = profiler.create_profile(
                                    endpoint=endpoint_key,
                                    method=request.method,
                                    metadata=parent._get_request_metadata(request),
                                )
                                parent.process_profile(profile)
                                logger.debug(
                                    f"Threshold exceeded for {path}: "
                                    f"{duration:.3f}s > {parent.config.threshold_seconds}s"
                                )
                            else:
                                logger.debug(
                                    f"Request {path} completed in {duration:.3f}s "
                                    f"(under threshold)"
                                )
                    except Exception as e:
                        logger.error(f"Error in profiler: {e}", exc_info=True)
                    finally:
                        _profiler_var.set(None)

        # Add middleware using FastAPI's add_middleware
        # This properly wraps the ASGI app without breaking route decorators
        app.add_middleware(ProfilerMiddleware)

        logger.debug(f"FastAPIMiddleware installed on app: {app.title}")

    def _build_endpoint_key(self, request: Request) -> str:
        """Build endpoint key for deduplication.

        Includes method, path, and query parameters for fine-grained deduplication.

        Args:
            request: The Starlette request object.

        Returns:
            Endpoint key string like "GET /api/users?id=1"
        """
        key = f"{request.method} {request.url.path}"

        if request.url.query:
            key = f"{key}?{request.url.query}"

        return key

    def _get_request_metadata(self, request: Request) -> Dict[str, Any]:
        """Get metadata from the current request.

        Args:
            request: The Starlette request object.

        Returns:
            Dictionary with request metadata.
        """
        metadata: Dict[str, Any] = {
            "url": str(request.url),
            "path": request.url.path,
            "method": request.method,
        }

        if request.client:
            metadata["remote_addr"] = request.client.host

        user_agent = request.headers.get("user-agent")
        if user_agent:
            metadata["user_agent"] = user_agent

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                metadata["content_length"] = int(content_length)
            except ValueError:
                pass

        if request.url.query:
            metadata["query_string"] = request.url.query

        if request.query_params:
            metadata["query_params"] = dict(request.query_params)

        if hasattr(request, "path_params") and request.path_params:
            metadata["path_params"] = dict(request.path_params)

        return metadata

    def _before_request(self) -> None:
        """Hook called before request processing.

        Note: In FastAPI, this is handled by the ASGI middleware.
        This method exists for interface compatibility.
        """
        pass

    def _after_request(self, response: Any) -> Any:
        """Hook called after request processing.

        Note: In FastAPI, this is handled by the ASGI middleware.
        This method exists for interface compatibility.

        Args:
            response: The response object.

        Returns:
            The response object (unmodified).
        """
        return response


def get_current_profiler() -> Optional["Profiler"]:
    """Get the profiler for the current request context.

    This can be used by other parts of the application to access
    the current profiler if needed.

    Returns:
        The current Profiler instance, or None if not in a profiled request.
    """
    return _profiler_var.get()
