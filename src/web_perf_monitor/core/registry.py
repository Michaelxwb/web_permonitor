"""Framework registry for adapter management.

This module provides the FrameworkRegistry singleton that manages
all registered framework adapters.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from .base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


class FrameworkRegistry:
    """Singleton registry for framework adapters.

    Manages registration and retrieval of framework adapters, enabling
    the system to support multiple web frameworks through a plugin architecture.

    Example:
        @FrameworkRegistry.register("flask")
        class FlaskAdapter(BaseAdapter):
            ...

        adapter_cls = FrameworkRegistry.get("flask")
        adapter = adapter_cls()
    """

    _adapters: Dict[str, Type["BaseAdapter"]] = {}
    _instances: Dict[str, "BaseAdapter"] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type["BaseAdapter"]], Type["BaseAdapter"]]:
        """Decorator to register a framework adapter.

        Args:
            name: The framework name (e.g., "flask", "django").

        Returns:
            Decorator function that registers the adapter class.

        Example:
            @FrameworkRegistry.register("flask")
            class FlaskAdapter(BaseAdapter):
                ...
        """

        def decorator(adapter_cls: Type["BaseAdapter"]) -> Type["BaseAdapter"]:
            cls._adapters[name] = adapter_cls
            logger.debug(f"Registered framework adapter: {name}")
            return adapter_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> Type["BaseAdapter"]:
        """Get a registered adapter class by name.

        Args:
            name: The framework name.

        Returns:
            The adapter class.

        Raises:
            KeyError: If no adapter is registered for the given name.
        """
        if name not in cls._adapters:
            raise KeyError(
                f"No adapter registered for framework '{name}'. "
                f"Available frameworks: {cls.list_frameworks()}"
            )
        return cls._adapters[name]

    @classmethod
    def get_instance(cls, name: str) -> "BaseAdapter":
        """Get or create an adapter instance.

        Args:
            name: The framework name.

        Returns:
            An adapter instance (cached).

        Raises:
            KeyError: If no adapter is registered for the given name.
        """
        if name not in cls._instances:
            adapter_cls = cls.get(name)
            cls._instances[name] = adapter_cls()
        return cls._instances[name]

    @classmethod
    def list_frameworks(cls) -> List[str]:
        """List all registered framework names.

        Returns:
            List of registered framework names.
        """
        return list(cls._adapters.keys())

    @classmethod
    def auto_detect(cls, app: Any) -> Optional["BaseAdapter"]:
        """Auto-detect the application type and return the appropriate adapter.

        Iterates through registered adapters and checks if any can handle
        the given application instance.

        Args:
            app: The application instance to detect.

        Returns:
            An adapter instance if detected, None otherwise.
        """
        # Check each registered adapter
        for name, adapter_cls in cls._adapters.items():
            try:
                adapter = cls.get_instance(name)
                if adapter.can_handle(app):
                    logger.debug(f"Auto-detected framework: {name}")
                    return adapter
            except Exception as e:
                logger.debug(f"Adapter {name} cannot handle app: {e}")
                continue

        logger.warning(
            f"Could not auto-detect framework for app type: {type(app).__name__}"
        )
        return None

    @classmethod
    def clear(cls) -> None:
        """Clear all registered adapters (mainly for testing)."""
        cls._adapters.clear()
        cls._instances.clear()

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a framework is registered.

        Args:
            name: The framework name.

        Returns:
            True if registered, False otherwise.
        """
        return name in cls._adapters
