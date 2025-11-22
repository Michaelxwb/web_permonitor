"""Flask framework integration for web-perfmonitor.

This module provides Flask-specific implementations for performance monitoring.

Public API:
    - FlaskAdapter: Framework adapter for Flask applications
    - FlaskMiddleware: Request profiling middleware
    - FlaskProfileDecorator: Function-level profiling decorator
"""

from .adapter import FlaskAdapter
from .decorator import FlaskProfileDecorator
from .middleware import FlaskMiddleware

__all__ = [
    "FlaskAdapter",
    "FlaskMiddleware",
    "FlaskProfileDecorator",
]
