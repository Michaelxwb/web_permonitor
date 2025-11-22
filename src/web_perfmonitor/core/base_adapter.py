"""Base adapter for framework integration.

This module defines the abstract base class for framework adapters,
which provide the interface between the monitoring system and specific
web frameworks like Flask or Django.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from ..config import MonitorConfig
    from .base_middleware import BaseMiddleware

# Generic type variables for framework-specific types
AppType = TypeVar("AppType")
RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")


class BaseAdapter(ABC, Generic[AppType, RequestType, ResponseType]):
    """Abstract base class for framework adapters.

    Adapters provide the bridge between the generic monitoring system
    and framework-specific implementations. Each supported framework
    (Flask, Django, etc.) must have its own adapter implementation.

    Generic Parameters:
        AppType: The framework's application type (e.g., Flask).
        RequestType: The framework's request type (e.g., werkzeug.local.LocalProxy).
        ResponseType: The framework's response type (e.g., flask.Response).

    Example:
        @FrameworkRegistry.register("flask")
        class FlaskAdapter(BaseAdapter[Flask, LocalProxy, Response]):
            def get_request_path(self, request: LocalProxy) -> str:
                return request.path
            ...
    """

    @abstractmethod
    def get_request_path(self, request: RequestType) -> str:
        """Extract the request path from a request object.

        Args:
            request: The framework-specific request object.

        Returns:
            The request path (e.g., "/api/users").
        """
        pass

    @abstractmethod
    def get_request_method(self, request: RequestType) -> str:
        """Extract the HTTP method from a request object.

        Args:
            request: The framework-specific request object.

        Returns:
            The HTTP method (e.g., "GET", "POST").
        """
        pass

    @abstractmethod
    def create_middleware(
        self, app: AppType, config: "MonitorConfig"
    ) -> "BaseMiddleware":
        """Create a framework-specific middleware instance.

        Args:
            app: The framework application instance.
            config: The monitoring configuration.

        Returns:
            A middleware instance for the framework.
        """
        pass

    @abstractmethod
    def create_decorator(self, config: "MonitorConfig") -> Callable[..., Any]:
        """Create a framework-specific profile decorator.

        Args:
            config: The monitoring configuration.

        Returns:
            A decorator function for profiling.
        """
        pass

    def can_handle(self, app: Any) -> bool:
        """Check if this adapter can handle the given application.

        Override this method to implement framework detection logic.
        The default implementation returns False.

        Args:
            app: The application instance to check.

        Returns:
            True if this adapter can handle the app, False otherwise.
        """
        return False

    def get_framework_name(self) -> str:
        """Get the name of the framework this adapter handles.

        Returns:
            The framework name (e.g., "flask", "django").
        """
        return self.__class__.__name__.replace("Adapter", "").lower()
