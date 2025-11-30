"""Sanic middleware for performance monitoring.

This module provides the Sanic-specific middleware implementation
for automatic request profiling.
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ...core import BaseMiddleware

if TYPE_CHECKING:
    from sanic import Sanic
    from sanic.request import Request
    from sanic.response import BaseHTTPResponse

    from ...config import MonitorConfig

logger = logging.getLogger(__name__)

# Maximum size for metadata values to prevent memory issues
MAX_METADATA_VALUE_SIZE = 10000


class SanicMiddleware(BaseMiddleware):
    """Sanic middleware for automatic request profiling.

    Hooks into Sanic's request lifecycle to automatically profile
    all requests (or filtered subset) and generate performance reports
    when thresholds are exceeded.

    The middleware uses Sanic's `request.ctx` object to store the profiler
    instance during request processing, ensuring proper async context handling.

    Attributes:
        config: The monitoring configuration.
        _app: The Sanic application instance (set after install).

    Example:
        from sanic import Sanic
        from web_perfmonitor import MonitorConfig
        from web_perfmonitor.frameworks.sanic import SanicMiddleware

        app = Sanic("MyApp")
        config = MonitorConfig(threshold_seconds=0.5)
        middleware = SanicMiddleware(config)
        middleware.install(app)
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the Sanic middleware.

        Args:
            config: The monitoring configuration.
        """
        super().__init__(config)
        self._app: "Optional[Sanic]" = None

    def install(self, app: "Sanic") -> None:
        """Install the middleware into a Sanic application.

        Registers request and response middleware handlers with the
        Sanic application.

        Args:
            app: The Sanic application instance.
        """
        self._app = app

        # Register request middleware (before request processing)
        app.register_middleware(self._before_request_wrapper, "request")

        # Register response middleware (after request processing)
        app.register_middleware(self._after_request_wrapper, "response")

        logger.debug(f"SanicMiddleware installed on app: {app.name}")

    async def _before_request_wrapper(self, request: "Request") -> None:
        """Wrapper for before request hook.

        Args:
            request: The Sanic request object.
        """
        # Check if this path should be profiled
        if not self.should_profile(request.path):
            logger.debug(
                f"Skipping profiling for blacklisted path: {request.method} {request.path}"
            )
            return

        try:
            from ...profiler import Profiler

            profiler = Profiler()
            profiler.start()
            request.ctx._perf_monitor_profiler = profiler
            logger.debug(f"Started profiling: {request.method} {request.path}")
        except Exception as e:
            # Never let profiling errors affect the application
            logger.error(f"Error starting profiler: {e}", exc_info=True)

    async def _after_request_wrapper(
        self, request: "Request", response: "BaseHTTPResponse"
    ) -> None:
        """Wrapper for after request hook.

        Args:
            request: The Sanic request object.
            response: The Sanic response object.
        """
        # Check if we have a profiler running
        profiler = getattr(request.ctx, "_perf_monitor_profiler", None)
        if profiler is None:
            return

        try:
            profiler.stop()
            duration = profiler.duration

            # Only create profile if threshold exceeded
            if duration > self.config.threshold_seconds:
                # Build endpoint key for deduplication
                endpoint_key = self._build_endpoint_key(request)
                profile = profiler.create_profile(
                    endpoint=endpoint_key,
                    method=request.method,
                    metadata=self._get_request_metadata(request),
                )
                self.process_profile(profile)
                logger.info(
                    f"Performance threshold exceeded: {request.method} {request.path} - "
                    f"{duration:.3f}s > {self.config.threshold_seconds}s"
                )
            else:
                logger.debug(
                    f"Request {request.path} completed in {duration:.3f}s (under threshold)"
                )
        except Exception as e:
            # Never let profiling errors affect the application
            logger.error(f"Error in profiler: {e}", exc_info=True)
        finally:
            # Clean up
            if hasattr(request.ctx, "_perf_monitor_profiler"):
                delattr(request.ctx, "_perf_monitor_profiler")

    def _build_endpoint_key(self, request: "Request") -> str:
        """Build endpoint key for deduplication.

        Includes method, path, query parameters, and request body hash
        for fine-grained deduplication.

        Args:
            request: The Sanic request object.

        Returns:
            Endpoint key string like "POST /api/users?id=1#body_hash"
        """
        # Start with method and path
        key = f"{request.method} {request.path}"

        # Add query string if present
        if request.query_string:
            key = f"{key}?{request.query_string}"

        # For POST/PUT/PATCH requests, include body hash for deduplication
        if request.method in ("POST", "PUT", "PATCH"):
            body_hash = self._get_body_hash(request)
            if body_hash:
                key = f"{key}#{body_hash}"

        return key

    def _get_body_hash(self, request: "Request") -> str:
        """Generate a hash of the request body for deduplication.

        Args:
            request: The Sanic request object.

        Returns:
            Short hash string of the request body, or empty string if no body.
        """
        import hashlib
        import json

        try:
            # Try JSON body first
            if request.json:
                body_str = json.dumps(request.json, sort_keys=True)
                return hashlib.md5(body_str.encode()).hexdigest()[:8]

            # Try form data
            if request.form:
                form_str = "&".join(f"{k}={v}" for k, v in sorted(request.form.items()))
                return hashlib.md5(form_str.encode()).hexdigest()[:8]

            # Try raw body
            if request.body:
                return hashlib.md5(request.body).hexdigest()[:8]

        except Exception:
            pass

        return ""

    def _get_request_metadata(self, request: "Request") -> Dict[str, Any]:
        """Get metadata from the current Sanic request.

        Limits value sizes to prevent memory issues with large payloads.

        Args:
            request: The Sanic request object.

        Returns:
            Dictionary with request metadata.
        """
        metadata: Dict[str, Any] = {
            "url": self._truncate_value(request.url),
            "path": request.path,
            "method": request.method,
            "remote_addr": request.ip,
        }

        # Add user agent if available
        user_agent = request.headers.get("User-Agent")
        if user_agent:
            metadata["user_agent"] = self._truncate_value(user_agent)

        # Add content length if available
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                metadata["content_length"] = int(content_length)
            except ValueError:
                pass

        # Add query string if present
        if request.query_string:
            metadata["query_string"] = self._truncate_value(request.query_string)

        # Add parsed query parameters as dict (with size limits)
        if request.args:
            metadata["query_params"] = self._truncate_dict(dict(request.args))

        # Add form data if present (for POST requests) - with size limits
        if request.form:
            metadata["form_data"] = self._truncate_dict(dict(request.form))

        # Add JSON body if present - with size limits
        try:
            if request.json:
                json_body = request.json
                # Limit JSON body size
                if isinstance(json_body, dict):
                    metadata["json_body"] = self._truncate_dict(json_body)
                elif isinstance(json_body, list) and len(json_body) > 100:
                    metadata["json_body"] = json_body[:100]
                    metadata["json_body_truncated"] = True
                else:
                    metadata["json_body"] = json_body
        except Exception:
            pass

        # Add request headers if enabled
        if self.config.capture_request_headers:
            request_headers = self._collect_request_headers(request)
            if request_headers:
                metadata["request_headers"] = request_headers

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

    def _collect_request_headers(self, request: "Request") -> Dict[str, str]:
        """Collect HTTP request headers based on configuration.

        Args:
            request: Sanic request object.

        Returns:
            Dictionary of header names to values.
        """
        # Default headers to collect if not configured
        default_headers = [
            "X-Forwarded-For",
            "X-Real-IP",
            "X-Request-ID",
            "X-Trace-ID",
            "X-Correlation-ID",
            "Referer",
            "Content-Type",
            "Accept",
            "Accept-Language",
            "Origin",
            "User-Agent",
        ]

        # Use configured headers or default
        headers_to_collect = self.config.included_headers or default_headers

        collected_headers: Dict[str, str] = {}
        for header_name in headers_to_collect:
            header_value = request.headers.get(header_name)
            if header_value:
                # Truncate header values to 500 characters
                collected_headers[header_name] = self._truncate_value(header_value, max_size=500)

        return collected_headers

    def _before_request(self) -> None:
        """Hook called before request processing.

        Not used in Sanic implementation - using async wrappers instead.
        """
        pass

    def _after_request(self, response: Any) -> Any:
        """Hook called after request processing.

        Not used in Sanic implementation - using async wrappers instead.

        Args:
            response: The response object.

        Returns:
            The response object (unmodified).
        """
        return response
