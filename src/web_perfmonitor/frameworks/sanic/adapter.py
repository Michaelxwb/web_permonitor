"""Sanic framework adapter.

This module provides the Sanic-specific implementation of the
framework adapter interface.
"""

from typing import Any, Callable, Optional, TYPE_CHECKING

from ...core import BaseAdapter, FrameworkRegistry

if TYPE_CHECKING:
    from sanic import Sanic
    from sanic.request import Request

    from ...config import MonitorConfig
    from .decorator import SanicProfileDecorator
    from .middleware import SanicMiddleware


@FrameworkRegistry.register("sanic")
class SanicAdapter(BaseAdapter["Sanic", "Request", Any]):
    """Sanic framework adapter.

    Provides the bridge between the generic monitoring system and
    Sanic-specific implementations.

    This adapter is automatically registered with the FrameworkRegistry
    and can be used for auto-detection of Sanic applications.

    Example:
        from web_perfmonitor import PerformanceMiddleware

        app = Sanic("MyApp")
        # Auto-detection will use SanicAdapter
        PerformanceMiddleware(app)
    """

    def get_request_path(self, request: "Request") -> str:
        """Extract the request path from a Sanic request.

        Args:
            request: The Sanic request object.

        Returns:
            The request path (e.g., "/api/users").
        """
        return request.path

    def get_request_method(self, request: "Request") -> str:
        """Extract the HTTP method from a Sanic request.

        Args:
            request: The Sanic request object.

        Returns:
            The HTTP method (e.g., "GET", "POST").
        """
        return request.method

    def create_middleware(
        self,
        app: "Sanic",
        config: "MonitorConfig",
    ) -> "SanicMiddleware":
        """Create a Sanic-specific middleware instance.

        Args:
            app: The Sanic application instance.
            config: The monitoring configuration.

        Returns:
            A SanicMiddleware instance installed on the app.
        """
        from .middleware import SanicMiddleware

        middleware = SanicMiddleware(config)
        middleware.install(app)
        return middleware

    def create_decorator(self, config: "MonitorConfig") -> Callable[..., Any]:
        """Create a Sanic-specific profile decorator factory.

        Args:
            config: The monitoring configuration.

        Returns:
            A decorator factory function.
        """
        from .decorator import SanicProfileDecorator

        def decorator_factory(
            threshold: Optional[float] = None,
            name: Optional[str] = None,
        ) -> "SanicProfileDecorator":
            return SanicProfileDecorator(
                config=config,
                threshold=threshold,
                name=name,
            )

        return decorator_factory

    def can_handle(self, app: Any) -> bool:
        """Check if this adapter can handle the given application.

        Detects Sanic applications by checking the class hierarchy.

        Args:
            app: The application instance to check.

        Returns:
            True if the app is a Sanic application, False otherwise.
        """
        try:
            from sanic import Sanic

            return isinstance(app, Sanic)
        except ImportError:
            return False

    def get_framework_name(self) -> str:
        """Get the name of the framework this adapter handles.

        Returns:
            The string "sanic".
        """
        return "sanic"
