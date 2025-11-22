"""FastAPI framework adapter.

This module provides the FastAPI-specific implementation of the
framework adapter interface.
"""

from typing import Any, Callable, Optional, TYPE_CHECKING

from ...core import BaseAdapter, FrameworkRegistry

if TYPE_CHECKING:
    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import Response

    from ...config import MonitorConfig
    from .decorator import FastAPIProfileDecorator
    from .middleware import FastAPIMiddleware


@FrameworkRegistry.register("fastapi")
class FastAPIAdapter(BaseAdapter["FastAPI", "Request", "Response"]):
    """FastAPI framework adapter.

    Provides the bridge between the generic monitoring system and
    FastAPI-specific implementations.

    This adapter is automatically registered with the FrameworkRegistry
    and can be used for auto-detection of FastAPI applications.

    Example:
        from web_perfmonitor import PerformanceMiddleware

        app = FastAPI()
        # Auto-detection will use FastAPIAdapter
        PerformanceMiddleware(app)
    """

    def get_request_path(self, request: "Request") -> str:
        """Extract the request path from a Starlette request.

        Args:
            request: The Starlette request object.

        Returns:
            The request path (e.g., "/api/users").
        """
        return request.url.path

    def get_request_method(self, request: "Request") -> str:
        """Extract the HTTP method from a Starlette request.

        Args:
            request: The Starlette request object.

        Returns:
            The HTTP method (e.g., "GET", "POST").
        """
        return request.method

    def create_middleware(
        self,
        app: "FastAPI",
        config: "MonitorConfig",
    ) -> "FastAPIMiddleware":
        """Create a FastAPI-specific middleware instance.

        Args:
            app: The FastAPI application instance.
            config: The monitoring configuration.

        Returns:
            A FastAPIMiddleware instance installed on the app.
        """
        from .middleware import FastAPIMiddleware

        middleware = FastAPIMiddleware(config)
        middleware.install(app)
        return middleware

    def create_decorator(self, config: "MonitorConfig") -> Callable[..., Any]:
        """Create a FastAPI-specific profile decorator factory.

        Args:
            config: The monitoring configuration.

        Returns:
            A decorator factory function.
        """
        from .decorator import FastAPIProfileDecorator

        def decorator_factory(
            threshold: Optional[float] = None,
            name: Optional[str] = None,
        ) -> "FastAPIProfileDecorator":
            return FastAPIProfileDecorator(
                config=config,
                threshold=threshold,
                name=name,
            )

        return decorator_factory

    def can_handle(self, app: Any) -> bool:
        """Check if this adapter can handle the given application.

        Detects FastAPI applications by checking the class hierarchy.

        Args:
            app: The application instance to check.

        Returns:
            True if the app is a FastAPI application, False otherwise.
        """
        try:
            from fastapi import FastAPI

            return isinstance(app, FastAPI)
        except ImportError:
            return False

    def get_framework_name(self) -> str:
        """Get the name of the framework this adapter handles.

        Returns:
            The string "fastapi".
        """
        return "fastapi"
