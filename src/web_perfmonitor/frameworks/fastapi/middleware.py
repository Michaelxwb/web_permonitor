"""FastAPI middleware for performance monitoring.

This module provides the FastAPI-specific middleware implementation
for automatic request profiling with async support.

Uses pure ASGI middleware instead of BaseHTTPMiddleware to ensure
pyinstrument can correctly capture the full async call stack.
"""

import logging
from contextvars import ContextVar, Token
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

# Maximum size for metadata values to prevent memory issues
MAX_METADATA_VALUE_SIZE = 10000


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
                method = request.method

                # Check if this path should be profiled
                if not parent.should_profile(path):
                    logger.debug(f"Skipping profiling for blacklisted path: {method} {path}")
                    await self.app(scope, receive, send)
                    return

                # For POST/PUT/PATCH, capture body for deduplication
                body_hash = ""
                body_bytes: bytes = b""
                if method in ("POST", "PUT", "PATCH"):
                    body_bytes = await self._read_body(receive)
                    body_hash = parent._compute_body_hash(body_bytes)

                    # Create a new receive that returns the cached body
                    async def receive_wrapper() -> Message:
                        return {"type": "http.request", "body": body_bytes, "more_body": False}
                else:
                    receive_wrapper = receive  # type: ignore

                # Start profiling
                profiler: Optional["Profiler"] = None
                token: Optional[Token] = None
                try:
                    from ...profiler import Profiler

                    profiler = Profiler()
                    profiler.start()
                    # Use token for proper ContextVar cleanup
                    token = _profiler_var.set(profiler)
                    logger.debug(f"Started profiling: {method} {path}")
                except Exception as e:
                    logger.error(f"Error starting profiler: {e}", exc_info=True)
                    await self.app(scope, receive_wrapper, send)
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
                    await self.app(scope, receive_wrapper, send_wrapper)
                finally:
                    # Stop profiler and process results
                    try:
                        if profiler is not None:
                            profiler.stop()
                            duration = profiler.duration

                            if duration > parent.config.threshold_seconds:
                                endpoint_key = parent._build_endpoint_key(request, body_hash)
                                profile = profiler.create_profile(
                                    endpoint=endpoint_key,
                                    method=method,
                                    metadata=parent._get_request_metadata(request),
                                )
                                parent.process_profile(profile)
                                logger.info(
                                    f"Performance threshold exceeded: {method} {path} - "
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
                        # Reset ContextVar using token for proper cleanup
                        if token is not None:
                            _profiler_var.reset(token)
                        else:
                            _profiler_var.set(None)
                        # Explicitly delete profiler reference
                        profiler = None

            async def _read_body(self, receive: Receive) -> bytes:
                """Read the entire request body."""
                body_parts = []
                while True:
                    message = await receive()
                    body = message.get("body", b"")
                    if body:
                        body_parts.append(body)
                    if not message.get("more_body", False):
                        break
                return b"".join(body_parts)

        # Add middleware using FastAPI's add_middleware
        # This properly wraps the ASGI app without breaking route decorators
        app.add_middleware(ProfilerMiddleware)

        logger.debug(f"FastAPIMiddleware installed on app: {app.title}")

    def _compute_body_hash(self, body: bytes) -> str:
        """Compute a hash of the request body for deduplication.

        Args:
            body: The request body bytes.

        Returns:
            Short hash string (8 characters) of the body.
        """
        import hashlib

        if not body:
            return ""

        try:
            return hashlib.md5(body).hexdigest()[:8]
        except Exception:
            return ""

    def _build_endpoint_key(self, request: Request, body_hash: str = "") -> str:
        """Build endpoint key for deduplication.

        Includes method, path, query parameters, and request body hash
        for fine-grained deduplication. This ensures POST requests with
        different body parameters are not incorrectly deduplicated.

        Args:
            request: The Starlette request object.
            body_hash: Hash of the request body (for POST/PUT/PATCH).

        Returns:
            Endpoint key string like "POST /api/users?id=1#body_hash"
        """
        key = f"{request.method} {request.url.path}"

        if request.url.query:
            key = f"{key}?{request.url.query}"

        # For POST/PUT/PATCH requests, include body hash for deduplication
        if request.method in ("POST", "PUT", "PATCH") and body_hash:
            key = f"{key}#{body_hash}"

        return key

    def _get_request_metadata(self, request: Request) -> Dict[str, Any]:
        """Get metadata from the current request.

        Limits value sizes to prevent memory issues with large payloads.

        Args:
            request: The Starlette request object.

        Returns:
            Dictionary with request metadata.
        """
        metadata: Dict[str, Any] = {
            "url": self._truncate_value(str(request.url)),
            "path": request.url.path,
            "method": request.method,
        }

        if request.client:
            metadata["remote_addr"] = request.client.host

        user_agent = request.headers.get("user-agent")
        if user_agent:
            metadata["user_agent"] = self._truncate_value(user_agent)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                metadata["content_length"] = int(content_length)
            except ValueError:
                pass

        if request.url.query:
            metadata["query_string"] = self._truncate_value(request.url.query)

        if request.query_params:
            # Limit query params to prevent large payloads
            params = dict(request.query_params)
            metadata["query_params"] = self._truncate_dict(params)

        if hasattr(request, "path_params") and request.path_params:
            metadata["path_params"] = dict(request.path_params)

        return metadata

    def _truncate_value(self, value: str, max_size: int = MAX_METADATA_VALUE_SIZE) -> str:
        """Truncate a string value if it exceeds max size.

        Args:
            value: The string value to truncate.
            max_size: Maximum allowed size.

        Returns:
            Truncated string with indicator if truncated.
        """
        if len(value) <= max_size:
            return value
        return value[:max_size] + "... [truncated]"

    def _truncate_dict(
        self, data: Dict[str, Any], max_items: int = 100, max_value_size: int = 1000
    ) -> Dict[str, Any]:
        """Truncate a dictionary to prevent memory issues.

        Args:
            data: The dictionary to truncate.
            max_items: Maximum number of items to keep.
            max_value_size: Maximum size for string values.

        Returns:
            Truncated dictionary.
        """
        result: Dict[str, Any] = {}
        for i, (key, value) in enumerate(data.items()):
            if i >= max_items:
                result["_truncated"] = f"... and {len(data) - max_items} more items"
                break
            if isinstance(value, str) and len(value) > max_value_size:
                result[key] = value[:max_value_size] + "... [truncated]"
            else:
                result[key] = value
        return result

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
