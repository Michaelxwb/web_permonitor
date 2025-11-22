"""Notification system for performance alerts.

This module provides the notifier registry and base classes for
implementing notification channels.

Public API:
    - BaseNotifier: Abstract base class for notifiers
    - register_notifier: Decorator to register custom notifiers
    - get_notifier: Factory function to get notifier by type
    - list_notifiers: List all registered notifier types
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Type

from .base import BaseNotifier

logger = logging.getLogger(__name__)

# Registry of notifier classes
_notifier_registry: Dict[str, Type[BaseNotifier]] = {}


def register_notifier(
    name: str,
) -> Callable[[Type[BaseNotifier]], Type[BaseNotifier]]:
    """Decorator to register a notifier class.

    Registers a notifier class with the given name, allowing it to be
    instantiated via the get_notifier() factory function.

    Args:
        name: The notifier type name (e.g., "local", "mattermost", "slack").

    Returns:
        Decorator function that registers the notifier class.

    Example:
        @register_notifier("slack")
        class SlackNotifier(BaseNotifier):
            def __init__(self, webhook_url: str, **kwargs):
                super().__init__(**kwargs)
                self.webhook_url = webhook_url

            def send(self, profile, format="markdown"):
                ...

            def validate_config(self) -> bool:
                return bool(self.webhook_url)
    """

    def decorator(cls: Type[BaseNotifier]) -> Type[BaseNotifier]:
        if name in _notifier_registry:
            logger.warning(
                f"Notifier '{name}' is already registered. "
                f"Overwriting with {cls.__name__}"
            )
        _notifier_registry[name] = cls
        logger.debug(f"Registered notifier: {name} -> {cls.__name__}")
        return cls

    return decorator


def get_notifier(
    notifier_type: str,
    **kwargs: Any,
) -> BaseNotifier:
    """Create a notifier instance by type.

    Factory function that creates a notifier instance based on the
    registered type name.

    Args:
        notifier_type: The notifier type name (e.g., "local", "mattermost").
        **kwargs: Configuration options passed to the notifier constructor.

    Returns:
        A configured notifier instance.

    Raises:
        KeyError: If the notifier type is not registered.

    Example:
        notifier = get_notifier(
            "mattermost",
            server_url="https://mm.example.com",
            token="xxx",
            channel_id="yyy"
        )
        notifier.send(profile)
    """
    if notifier_type not in _notifier_registry:
        raise KeyError(
            f"Notifier type '{notifier_type}' is not registered. "
            f"Available types: {list_notifiers()}"
        )

    notifier_cls = _notifier_registry[notifier_type]
    return notifier_cls(**kwargs)


def list_notifiers() -> List[str]:
    """List all registered notifier types.

    Returns:
        List of registered notifier type names.
    """
    return list(_notifier_registry.keys())


def is_registered(name: str) -> bool:
    """Check if a notifier type is registered.

    Args:
        name: The notifier type name.

    Returns:
        True if registered, False otherwise.
    """
    return name in _notifier_registry


def get_notifier_class(name: str) -> Optional[Type[BaseNotifier]]:
    """Get a notifier class by name without instantiating.

    Args:
        name: The notifier type name.

    Returns:
        The notifier class, or None if not registered.
    """
    return _notifier_registry.get(name)


__all__ = [
    "BaseNotifier",
    "register_notifier",
    "get_notifier",
    "list_notifiers",
    "is_registered",
    "get_notifier_class",
]

# Import notifiers to trigger registration
from . import local  # noqa: F401
from . import mattermost  # noqa: F401
from . import email  # noqa: F401
