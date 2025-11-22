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

        Registers before_request and after_request handlers with
        the Flask application.

        Args:
            app: The Flask application instance.
        """
        self._app = app
        app.before_request(self._before_request)
        app.after_request(self._after_request)
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

    def _build_endpoint_key(self) -> str:
        """Build endpoint key for deduplication.

        Includes method, path, and query parameters for fine-grained deduplication.

        Returns:
            Endpoint key string like "GET /api/users?id=1"
        """
        from flask import request

        # Start with method and path
        key = f"{request.method} {request.path}"

        # Add query string if present
        if request.query_string:
            query = request.query_string.decode("utf-8", errors="ignore")
            key = f"{key}?{query}"

        return key

    def _get_request_metadata(self) -> Dict[str, Any]:
        """Get metadata from the current Flask request.

        Returns:
            Dictionary with request metadata.
        """
        from flask import request

        metadata: Dict[str, Any] = {
            "url": request.url,
            "path": request.path,
            "method": request.method,
            "remote_addr": request.remote_addr,
        }

        # Add user agent if available
        if request.user_agent:
            metadata["user_agent"] = request.user_agent.string

        # Add content length if available
        if request.content_length:
            metadata["content_length"] = request.content_length

        # Add query string if present
        if request.query_string:
            metadata["query_string"] = request.query_string.decode("utf-8", errors="ignore")

        # Add parsed query parameters as dict
        if request.args:
            metadata["query_params"] = dict(request.args)

        # Add form data if present (for POST requests)
        if request.form:
            metadata["form_data"] = dict(request.form)

        # Add JSON body if present
        try:
            if request.is_json and request.json:
                metadata["json_body"] = request.json
        except Exception:
            pass

        return metadata
