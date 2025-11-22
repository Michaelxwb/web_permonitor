"""Local file notifier for performance reports.

This module provides a notifier that saves performance reports
to the local filesystem.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ..exceptions import NotificationError
from . import register_notifier
from .base import BaseNotifier

if TYPE_CHECKING:
    from ..models import PerformanceProfile

logger = logging.getLogger(__name__)


@register_notifier("local")
class LocalNotifier(BaseNotifier):
    """Notifier that saves performance reports to local files.

    Saves HTML and text reports to the configured output directory.
    Files are named using the pattern: {endpoint_safe}_{timestamp}_{id}.{ext}

    Attributes:
        output_dir: Directory where reports are saved.
        format: Output format ("markdown", "text", or "html").

    Example:
        notifier = LocalNotifier(
            output_dir="/var/log/perf-reports",
            format="markdown"
        )
        notifier.send(profile)
    """

    def __init__(
        self,
        output_dir: Optional[str] = None,
        format: str = "markdown",
        **kwargs,
    ) -> None:
        """Initialize the local notifier.

        Args:
            output_dir: Directory for saving reports. Defaults to /tmp.
            format: Output format ("markdown", "text", or "html").
            **kwargs: Additional configuration options.
        """
        super().__init__(output_dir=output_dir, format=format, **kwargs)
        self.output_dir = output_dir or "/tmp"
        self.format = format

    def send(
        self,
        profile: "PerformanceProfile",
        format: Optional[str] = None,
    ) -> None:
        """Save performance report to local file.

        Creates the output directory if it doesn't exist, then saves
        the report in the specified format.

        Args:
            profile: The performance profile to save.
            format: Message format override ("markdown", "text", "html").
                   Uses instance format if not specified.

        Raises:
            NotificationError: If saving fails (e.g., permission denied).
        """
        actual_format = format or self.format

        try:
            # Ensure output directory exists
            self._ensure_directory()

            # Generate filename
            filename = self._generate_filename(profile, actual_format)
            filepath = Path(self.output_dir) / filename

            # Generate content based on format
            if actual_format == "html":
                content = self._generate_html(profile)
            elif actual_format == "text":
                content = self._format_text(profile)
            else:  # markdown
                content = self._format_markdown(profile)

            # Write file
            filepath.write_text(content, encoding="utf-8")
            logger.info(f"Performance report saved to: {filepath}")

        except OSError as e:
            error_msg = f"Failed to save report to {self.output_dir}: {e}"
            logger.error(error_msg)
            raise NotificationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error saving report: {e}"
            logger.error(error_msg, exc_info=True)
            raise NotificationError(error_msg) from e

    def validate_config(self) -> bool:
        """Validate the notifier configuration.

        Checks that the output directory can be written to.

        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            # Check if directory exists or can be created
            path = Path(self.output_dir)
            if path.exists():
                return path.is_dir() and os.access(path, os.W_OK)
            else:
                # Check if parent is writable
                parent = path.parent
                return parent.exists() and os.access(parent, os.W_OK)
        except Exception as e:
            logger.warning(f"Config validation failed: {e}")
            return False

    def _ensure_directory(self) -> None:
        """Ensure the output directory exists.

        Creates the directory and any parent directories if needed.

        Raises:
            OSError: If directory creation fails.
        """
        path = Path(self.output_dir)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created output directory: {path}")

    def _generate_filename(
        self,
        profile: "PerformanceProfile",
        format: str,
    ) -> str:
        """Generate a filename for the report.

        Format: {endpoint_safe}_{id}.{ext}

        Args:
            profile: The performance profile.
            format: The output format.

        Returns:
            Generated filename.
        """
        # Strip HTTP method prefix from endpoint (e.g., "GET /path" -> "/path")
        endpoint = profile.endpoint
        http_methods = ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS ")
        for method in http_methods:
            if endpoint.startswith(method):
                endpoint = endpoint[len(method):]
                break

        # Sanitize endpoint for filename
        endpoint_safe = self._sanitize_filename(endpoint)

        # Determine extension
        ext_map = {
            "html": "html",
            "markdown": "md",
            "text": "txt",
        }
        ext = ext_map.get(format, "txt")

        # Use short ID (first 8 chars)
        short_id = profile.id[:8]

        return f"{endpoint_safe}_{short_id}.{ext}"

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use in a filename.

        Replaces unsafe characters with underscores.

        Args:
            name: The string to sanitize.

        Returns:
            Sanitized string safe for filenames.
        """
        # Replace path separators and other unsafe chars
        sanitized = re.sub(r"[/\\?%*:|\"<>]", "_", name)
        # Replace multiple underscores with single
        sanitized = re.sub(r"_+", "_", sanitized)
        # Strip leading/trailing underscores
        sanitized = sanitized.strip("_")
        # Limit length
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        return sanitized or "unknown"

    def _generate_html(self, profile: "PerformanceProfile") -> str:
        """Generate HTML report with embedded pyinstrument output.

        Args:
            profile: The performance profile.

        Returns:
            HTML content string.
        """
        # If profile has HTML report from pyinstrument, use it as base
        if profile.html_report:
            # Wrap with additional metadata
            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Performance Report: {profile.endpoint}</title>
    <style>
        .metadata {{
            background: #f5f5f5;
            padding: 1em;
            margin-bottom: 1em;
            border-radius: 4px;
        }}
        .metadata h2 {{
            margin-top: 0;
        }}
        .metadata dl {{
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 0.5em 1em;
        }}
        .metadata dt {{
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="metadata">
        <h2>Performance Alert: {profile.endpoint}</h2>
        <dl>
            <dt>Method</dt><dd>{profile.method}</dd>
            <dt>Duration</dt><dd>{profile.duration_seconds:.3f}s</dd>
            <dt>Timestamp</dt><dd>{profile.timestamp.isoformat()}</dd>
            <dt>ID</dt><dd>{profile.id}</dd>
        </dl>
    </div>
    {profile.html_report}
</body>
</html>"""

        # Fallback to text-based HTML
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Performance Report: {profile.endpoint}</title>
</head>
<body>
    <h1>Performance Alert: {profile.endpoint}</h1>
    <p>Method: {profile.method}</p>
    <p>Duration: {profile.duration_seconds:.3f}s</p>
    <p>Timestamp: {profile.timestamp.isoformat()}</p>
    <pre>{profile.text_report}</pre>
</body>
</html>"""
