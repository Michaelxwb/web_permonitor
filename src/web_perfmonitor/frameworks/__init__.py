"""Framework integrations for web-perfmonitor.

This module provides automatic framework discovery and registration.
When imported, it registers all available framework adapters with
the FrameworkRegistry.

Supported Frameworks:
    - Flask: Full support for request profiling and decorators
    - FastAPI: Full support for async request profiling and decorators
    - Sanic: Full support for async request profiling and decorators

Example:
    # Importing this module registers all adapters
    from web_perfmonitor import frameworks

    # Or just import the main package, which does this automatically
    from web_perfmonitor import PerformanceMiddleware
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Auto-discover and register framework adapters
# Each framework module registers itself via @FrameworkRegistry.register
_discovered_frameworks: List[str] = []


def _discover_flask() -> bool:
    """Attempt to discover and register Flask adapter."""
    try:
        from . import flask  # noqa: F401

        _discovered_frameworks.append("flask")
        logger.debug("Discovered Flask framework adapter")
        return True
    except ImportError:
        logger.debug("Flask not available, skipping adapter registration")
        return False


def _discover_fastapi() -> bool:
    """Attempt to discover and register FastAPI adapter."""
    try:
        from . import fastapi  # noqa: F401

        _discovered_frameworks.append("fastapi")
        logger.debug("Discovered FastAPI framework adapter")
        return True
    except ImportError:
        logger.debug("FastAPI not available, skipping adapter registration")
        return False


def _discover_sanic() -> bool:
    """Attempt to discover and register Sanic adapter."""
    try:
        from . import sanic  # noqa: F401

        _discovered_frameworks.append("sanic")
        logger.debug("Discovered Sanic framework adapter")
        return True
    except ImportError:
        logger.debug("Sanic not available, skipping adapter registration")
        return False


def discover_frameworks() -> List[str]:
    """Discover and register all available framework adapters.

    Returns:
        List of discovered framework names.
    """
    global _discovered_frameworks

    if not _discovered_frameworks:
        _discover_flask()
        _discover_fastapi()
        _discover_sanic()

    return _discovered_frameworks.copy()


# Auto-discover on import
discover_frameworks()


__all__ = [
    "discover_frameworks",
]
