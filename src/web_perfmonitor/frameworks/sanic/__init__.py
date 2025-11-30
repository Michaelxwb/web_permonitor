"""Sanic framework integration for web performance monitoring.

This module provides Sanic-specific implementations of the monitoring
system components.
"""

# Import adapter to trigger registration with FrameworkRegistry
from . import adapter  # noqa: F401

__all__ = ["adapter"]
