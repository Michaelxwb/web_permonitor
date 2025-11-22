"""Core framework abstraction layer.

This module provides the abstract base classes and registry for
implementing multi-framework support.

Public API:
    - FrameworkRegistry: Singleton registry for framework adapters
    - BaseAdapter: Abstract base class for framework adapters
    - BaseMiddleware: Abstract base class for middleware implementations
    - BaseDecorator: Abstract base class for profiling decorators

Example:
    # Implementing support for a new framework
    from web_perfmonitor.core import (
        FrameworkRegistry,
        BaseAdapter,
        BaseMiddleware,
        BaseDecorator,
    )

    @FrameworkRegistry.register("django")
    class DjangoAdapter(BaseAdapter[WSGIHandler, HttpRequest, HttpResponse]):
        ...
"""

from .base_adapter import BaseAdapter
from .base_decorator import BaseDecorator
from .base_middleware import BaseMiddleware
from .registry import FrameworkRegistry

__all__ = [
    "FrameworkRegistry",
    "BaseAdapter",
    "BaseMiddleware",
    "BaseDecorator",
]
