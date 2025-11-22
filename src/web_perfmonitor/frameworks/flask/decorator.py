"""Flask profile decorator for function-level monitoring.

This module provides the Flask-specific implementation of the
function-level profiling decorator.
"""

import logging
from typing import Any, Dict

from ...core import BaseDecorator

logger = logging.getLogger(__name__)


class FlaskProfileDecorator(BaseDecorator):
    """Flask-specific function profiling decorator.

    Profiles decorated functions and generates performance reports
    when execution time exceeds the configured threshold.

    This decorator preserves the original function's signature and
    docstring using functools.wraps (handled by BaseDecorator).

    If called within a Flask request context, additional context
    information (request path, method, user agent) is captured.

    Example:
        from web_perfmonitor import profile

        @profile()
        def slow_function():
            # This function will be profiled
            time.sleep(2)
            return "done"

        @profile(threshold=0.1, name="critical_db_query")
        def query_database():
            # Custom threshold and name
            return db.execute(query)
    """

    def _get_context(self) -> Dict[str, Any]:
        """Get Flask-specific context information.

        If the function is called within a Flask request context,
        captures request information. Otherwise, returns an empty dict.

        Returns:
            Dictionary with context data from Flask request, if available.
        """
        context: Dict[str, Any] = {}

        try:
            from flask import has_request_context, request

            if has_request_context():
                context["request_path"] = request.path
                context["request_method"] = request.method
                context["request_url"] = request.url

                if request.user_agent:
                    context["user_agent"] = request.user_agent.string

                if request.remote_addr:
                    context["remote_addr"] = request.remote_addr

                if request.endpoint:
                    context["flask_endpoint"] = request.endpoint

        except ImportError:
            # Flask not available
            logger.debug("Flask not available for context extraction")
        except Exception as e:
            # Don't let context extraction errors affect profiling
            logger.debug(f"Error extracting Flask context: {e}")

        return context
