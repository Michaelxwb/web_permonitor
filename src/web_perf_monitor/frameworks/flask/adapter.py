"""Flask framework adapter.

This module provides the Flask-specific implementation of the
framework adapter interface.
"""

from typing import Any, Callable, Optional, TYPE_CHECKING

from ...core import BaseAdapter, FrameworkRegistry

if TYPE_CHECKING:
    from flask import Flask, Response
    from werkzeug.local import LocalProxy

    from ...config import MonitorConfig
    from .decorator import FlaskProfileDecorator
    from .middleware import FlaskMiddleware


@FrameworkRegistry.register("flask")
class FlaskAdapter(BaseAdapter["Flask", "LocalProxy", "Response"]):
    """Flask framework adapter.

    Provides the bridge between the generic monitoring system and
    Flask-specific implementations.

    This adapter is automatically registered with the FrameworkRegistry
    and can be used for auto-detection of Flask applications.

    Example:
        from web_perf_monitor import PerformanceMiddleware

        app = Flask(__name__)
        # Auto-detection will use FlaskAdapter
        PerformanceMiddleware(app)
    """

    def get_request_path(self, request: "LocalProxy") -> str:
        """Extract the request path from a Flask request.

        Args:
            request: The Flask request proxy object.

        Returns:
            The request path (e.g., "/api/users").
        """
        return request.path

    def get_request_method(self, request: "LocalProxy") -> str:
        """Extract the HTTP method from a Flask request.

        Args:
            request: The Flask request proxy object.

        Returns:
            The HTTP method (e.g., "GET", "POST").
        """
        return request.method

    def create_middleware(
        self,
        app: "Flask",
        config: "MonitorConfig",
    ) -> "FlaskMiddleware":
        """Create a Flask-specific middleware instance.

        Args:
            app: The Flask application instance.
            config: The monitoring configuration.

        Returns:
            A FlaskMiddleware instance installed on the app.
        """
        from .middleware import FlaskMiddleware

        middleware = FlaskMiddleware(config)
        middleware.install(app)
        return middleware

    def create_decorator(self, config: "MonitorConfig") -> Callable[..., Any]:
        """Create a Flask-specific profile decorator factory.

        Args:
            config: The monitoring configuration.

        Returns:
            A decorator factory function.
        """
        from .decorator import FlaskProfileDecorator

        def decorator_factory(
            threshold: Optional[float] = None,
            name: Optional[str] = None,
        ) -> "FlaskProfileDecorator":
            return FlaskProfileDecorator(
                config=config,
                threshold=threshold,
                name=name,
            )

        return decorator_factory

    def can_handle(self, app: Any) -> bool:
        """Check if this adapter can handle the given application.

        Detects Flask applications by checking the class hierarchy.

        Args:
            app: The application instance to check.

        Returns:
            True if the app is a Flask application, False otherwise.
        """
        try:
            from flask import Flask

            return isinstance(app, Flask)
        except ImportError:
            return False

    def get_framework_name(self) -> str:
        """Get the name of the framework this adapter handles.

        Returns:
            The string "flask".
        """
        return "flask"
