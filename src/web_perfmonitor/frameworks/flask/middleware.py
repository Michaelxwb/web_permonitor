"""Flask middleware for performance monitoring.

This module provides the Flask-specific middleware implementation
for automatic request profiling.
"""

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ...core import BaseMiddleware

if TYPE_CHECKING:
    from flask import Flask, Response

    from ...config import MonitorConfig

logger = logging.getLogger(__name__)

# Maximum size for metadata values to prevent memory issues
MAX_METADATA_VALUE_SIZE = 10000


class FlaskMiddleware(BaseMiddleware):
    """Flask middleware for automatic request profiling.

    Hooks into Flask's request lifecycle to automatically profile
    all requests (or filtered subset) and generate performance reports
    when thresholds are exceeded.

    The middleware uses Flask's `g` object to store the profiler instance
    during request processing, ensuring thread-safety.

    Attributes:
        config: The monitoring configuration.
        _app: The Flask application instance (set after install).

    Example:
        from flask import Flask
        from web_perfmonitor import MonitorConfig
        from web_perfmonitor.frameworks.flask import FlaskMiddleware

        app = Flask(__name__)
        config = MonitorConfig(threshold_seconds=0.5)
        middleware = FlaskMiddleware(config)
        middleware.install(app)
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the Flask middleware.

        Args:
            config: The monitoring configuration.
        """
        super().__init__(config)
        self._app: "Optional[Flask]" = None

    def install(self, app: "Flask") -> None:
        """Install the middleware into a Flask application.

        Registers before_request, after_request, and teardown_request
        handlers with the Flask application.

        Args:
            app: The Flask application instance.
        """
        self._app = app
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        app.teardown_request(self._teardown_request)
        logger.debug(f"FlaskMiddleware installed on app: {app.name}")

    def _before_request(self) -> None:
        """Hook called before request processing.

        Starts the profiler if the request path should be profiled.
        Stores the profiler in Flask's g object for thread-safety.
        """
        from flask import g, request

        # Check if this path should be profiled
        if not self.should_profile(request.path):
            return

        try:
            from ...profiler import Profiler

            profiler = Profiler()
            profiler.start()
            g._perf_monitor_profiler = profiler
            logger.debug(f"Started profiling: {request.method} {request.path}")
        except Exception as e:
            # Never let profiling errors affect the application
            logger.error(f"Error starting profiler: {e}", exc_info=True)

    def _after_request(self, response: "Response") -> "Response":
        """Hook called after request processing.

        Stops the profiler, checks thresholds, and processes the profile
        if the duration exceeded the threshold.

        Args:
            response: The Flask response object.

        Returns:
            The response object (unmodified - zero intrusion).
        """
        from flask import g, request

        # Check if we have a profiler running
        profiler = getattr(g, "_perf_monitor_profiler", None)
        if profiler is None:
            return response

        try:
            profiler.stop()
            duration = profiler.duration

            # Only create profile if threshold exceeded
            if duration > self.config.threshold_seconds:
                # Build endpoint key for deduplication (method + path + query)
                endpoint_key = self._build_endpoint_key()
                profile = profiler.create_profile(
                    endpoint=endpoint_key,
                    method=request.method,
                    metadata=self._get_request_metadata(),
                )
                self.process_profile(profile)
                logger.debug(
                    f"Threshold exceeded for {request.path}: "
                    f"{duration:.3f}s > {self.config.threshold_seconds}s"
                )
            else:
                logger.debug(
                    f"Request {request.path} completed in {duration:.3f}s "
                    f"(under threshold)"
                )
        except Exception as e:
            # Never let profiling errors affect the application
            logger.error(f"Error in profiler: {e}", exc_info=True)
        finally:
            # Clean up
            if hasattr(g, "_perf_monitor_profiler"):
                delattr(g, "_perf_monitor_profiler")

        # Return response unmodified (zero intrusion)
        return response

    def _teardown_request(self, exception: Optional[Exception] = None) -> None:
        """Hook called after request is complete, even if an exception occurred.

        Ensures profiler is always cleaned up to prevent memory leaks.
        This is a safety net for cases where after_request might not be called.

        Args:
            exception: The exception that occurred, if any.
        """
        from flask import g

        # Ensure profiler is cleaned up even if after_request didn't run
        profiler = getattr(g, "_perf_monitor_profiler", None)
        if profiler is not None:
            try:
                # Stop profiler if still running
                if hasattr(profiler, "_profiler") and profiler._profiler.is_running:
                    profiler.stop()
                    logger.debug("Profiler stopped in teardown (exception occurred)")
            except Exception as e:
                logger.debug(f"Error stopping profiler in teardown: {e}")
            finally:
                # Always clean up the reference
                if hasattr(g, "_perf_monitor_profiler"):
                    delattr(g, "_perf_monitor_profiler")

    def _build_endpoint_key(self) -> str:
        """Build endpoint key for deduplication.

        Includes method, path, query parameters, and request body hash
        for fine-grained deduplication. This ensures POST requests with
        different body parameters are not incorrectly deduplicated.

        Returns:
            Endpoint key string like "POST /api/users?id=1#body_hash"
        """
        import hashlib
        from flask import request

        # Start with method and path
        key = f"{request.method} {request.path}"

        # Add query string if present
        if request.query_string:
            query = request.query_string.decode("utf-8", errors="ignore")
            key = f"{key}?{query}"

        # For POST/PUT/PATCH requests, include body hash for deduplication
        if request.method in ("POST", "PUT", "PATCH"):
            body_hash = self._get_body_hash()
            if body_hash:
                key = f"{key}#{body_hash}"

        return key

    def _get_body_hash(self) -> str:
        """Generate a hash of the request body for deduplication.

        Returns:
            Short hash string of the request body, or empty string if no body.
        """
        import hashlib
        import json
        from flask import request

        try:
            # Try JSON body first
            if request.is_json and request.json:
                body_str = json.dumps(request.json, sort_keys=True)
                return hashlib.md5(body_str.encode()).hexdigest()[:8]

            # Try form data
            if request.form:
                form_str = "&".join(f"{k}={v}" for k, v in sorted(request.form.items()))
                return hashlib.md5(form_str.encode()).hexdigest()[:8]

            # Try raw data
            if request.data:
                return hashlib.md5(request.data).hexdigest()[:8]

        except Exception:
            pass

        return ""

    def _get_request_metadata(self) -> Dict[str, Any]:
        """Get metadata from the current Flask request.

        Limits value sizes to prevent memory issues with large payloads.

        Returns:
            Dictionary with request metadata.
        """
        from flask import request

        metadata: Dict[str, Any] = {
            "url": self._truncate_value(request.url),
            "path": request.path,
            "method": request.method,
            "remote_addr": request.remote_addr,
        }

        # Add user agent if available
        if request.user_agent:
            metadata["user_agent"] = self._truncate_value(request.user_agent.string)

        # Add content length if available
        if request.content_length:
            metadata["content_length"] = request.content_length

        # Add query string if present
        if request.query_string:
            query_str = request.query_string.decode("utf-8", errors="ignore")
            metadata["query_string"] = self._truncate_value(query_str)

        # Add parsed query parameters as dict (with size limits)
        if request.args:
            metadata["query_params"] = self._truncate_dict(dict(request.args))

        # Add form data if present (for POST requests) - with size limits
        if request.form:
            metadata["form_data"] = self._truncate_dict(dict(request.form))

        # Add JSON body if present - with size limits
        try:
            if request.is_json and request.json:
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
