"""URL filtering for performance monitoring.

This module provides the UrlFilter class for controlling which
URLs should be monitored based on whitelist/blacklist rules.
"""

import fnmatch
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class UrlFilter:
    """URL filter with whitelist and blacklist support.

    Controls which URLs should be monitored based on pattern matching.
    Uses fnmatch for glob-style pattern matching (*, ?, []).

    Rules:
        - If whitelist is set, only matching URLs are monitored
        - If only blacklist is set, all URLs except matching ones are monitored
        - Whitelist takes precedence over blacklist

    Attributes:
        whitelist: List of URL patterns to include.
        blacklist: List of URL patterns to exclude.

    Example:
        # Only monitor /api/* endpoints
        filter = UrlFilter(whitelist=["/api/*"])

        # Monitor everything except health checks
        filter = UrlFilter(blacklist=["/health", "/ready"])

        # Check if a URL should be monitored
        if filter.should_monitor("/api/users"):
            profile_request()
    """

    def __init__(
        self,
        whitelist: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None,
    ) -> None:
        """Initialize the URL filter.

        Args:
            whitelist: List of URL patterns to include (glob syntax).
            blacklist: List of URL patterns to exclude (glob syntax).
        """
        self.whitelist = whitelist or []
        self.blacklist = blacklist or []
        self._validate_patterns()

    def should_monitor(self, path: str) -> bool:
        """Determine if a URL path should be monitored.

        Args:
            path: The URL path to check (e.g., "/api/users").

        Returns:
            True if the path should be monitored, False otherwise.
        """
        # If whitelist is set, only monitor matching paths
        if self.whitelist:
            return self._matches_any(path, self.whitelist)

        # If only blacklist is set, monitor everything except matches
        if self.blacklist:
            return not self._matches_any(path, self.blacklist)

        # No filters set, monitor everything
        return True

    def _matches_any(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any of the patterns.

        Args:
            path: The URL path to check.
            patterns: List of patterns to match against.

        Returns:
            True if path matches any pattern.
        """
        for pattern in patterns:
            try:
                if self._matches_pattern(path, pattern):
                    return True
            except Exception as e:
                logger.warning(f"Error matching pattern '{pattern}': {e}")
                continue
        return False

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a single pattern.

        Supports:
            - Exact match: "/api/users"
            - Glob patterns: "/api/*", "/api/users/?"
            - Character sets: "/api/v[12]/*"

        Args:
            path: The URL path to check.
            pattern: The pattern to match against.

        Returns:
            True if path matches the pattern.
        """
        # Exact match
        if path == pattern:
            return True

        # fnmatch for glob-style matching
        return fnmatch.fnmatch(path, pattern)

    def _validate_patterns(self) -> None:
        """Validate all patterns and log warnings for invalid ones."""
        for pattern in self.whitelist:
            if not self._is_valid_pattern(pattern):
                logger.warning(f"Invalid whitelist pattern: {pattern}")

        for pattern in self.blacklist:
            if not self._is_valid_pattern(pattern):
                logger.warning(f"Invalid blacklist pattern: {pattern}")

    def _is_valid_pattern(self, pattern: str) -> bool:
        """Check if a pattern is valid.

        Args:
            pattern: The pattern to validate.

        Returns:
            True if the pattern is valid.
        """
        if not pattern:
            return False

        # Check for unbalanced brackets
        bracket_depth = 0
        for char in pattern:
            if char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth -= 1
                if bracket_depth < 0:
                    return False

        return bracket_depth == 0

    def add_whitelist(self, pattern: str) -> None:
        """Add a pattern to the whitelist.

        Args:
            pattern: The pattern to add.
        """
        if pattern not in self.whitelist:
            if not self._is_valid_pattern(pattern):
                logger.warning(f"Adding invalid whitelist pattern: {pattern}")
            self.whitelist.append(pattern)

    def add_blacklist(self, pattern: str) -> None:
        """Add a pattern to the blacklist.

        Args:
            pattern: The pattern to add.
        """
        if pattern not in self.blacklist:
            if not self._is_valid_pattern(pattern):
                logger.warning(f"Adding invalid blacklist pattern: {pattern}")
            self.blacklist.append(pattern)

    def remove_whitelist(self, pattern: str) -> bool:
        """Remove a pattern from the whitelist.

        Args:
            pattern: The pattern to remove.

        Returns:
            True if the pattern was removed, False if not found.
        """
        try:
            self.whitelist.remove(pattern)
            return True
        except ValueError:
            return False

    def remove_blacklist(self, pattern: str) -> bool:
        """Remove a pattern from the blacklist.

        Args:
            pattern: The pattern to remove.

        Returns:
            True if the pattern was removed, False if not found.
        """
        try:
            self.blacklist.remove(pattern)
            return True
        except ValueError:
            return False

    def clear(self) -> None:
        """Clear all whitelist and blacklist patterns."""
        self.whitelist.clear()
        self.blacklist.clear()
