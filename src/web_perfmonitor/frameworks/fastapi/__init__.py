"""FastAPI framework integration for web-perfmonitor.

This module provides FastAPI-specific implementations for performance monitoring,
including middleware, adapters, and decorators that support async/await.

Example:
    from fastapi import FastAPI
    from web_perfmonitor import PerformanceMiddleware

    app = FastAPI()
    PerformanceMiddleware(app)  # Auto-detects FastAPI
"""

from .adapter import FastAPIAdapter
from .decorator import FastAPIProfileDecorator
from .middleware import FastAPIMiddleware

__all__ = [
    "FastAPIAdapter",
    "FastAPIMiddleware",
    "FastAPIProfileDecorator",
]
