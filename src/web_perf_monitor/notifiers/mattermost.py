"""Mattermost notifier for performance alerts.

This module provides a notifier that sends performance alerts
to a Mattermost channel.
"""

import logging
from typing import Any, Optional, TYPE_CHECKING

from ..exceptions import NotificationError
from . import register_notifier
from .base import BaseNotifier

if TYPE_CHECKING:
    from ..models import PerformanceProfile

logger = logging.getLogger(__name__)


@register_notifier("mattermost")
class MattermostNotifier(BaseNotifier):
    """Notifier that sends performance alerts to Mattermost.

    Uses the mattermostdriver library to send messages to a
    configured Mattermost channel.

    Attributes:
        server_url: The Mattermost server URL.
        token: The API token for authentication.
        channel_id: The target channel ID.
        format: Message format ("markdown" or "text").

    Example:
        notifier = MattermostNotifier(
            server_url="https://mattermost.example.com",
            token="your-api-token",
            channel_id="channel-id-here",
            format="markdown"
        )
        notifier.send(profile)
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        token: Optional[str] = None,
        channel_id: Optional[str] = None,
        format: str = "markdown",
        **kwargs: Any,
    ) -> None:
        """Initialize the Mattermost notifier.

        Args:
            server_url: The Mattermost server URL.
            token: The API token for authentication.
            channel_id: The target channel ID.
            format: Message format ("markdown" or "text").
            **kwargs: Additional configuration options.
        """
        super().__init__(
            server_url=server_url,
            token=token,
            channel_id=channel_id,
            format=format,
            **kwargs,
        )
        self.server_url = server_url or ""
        self.token = token or ""
        self.channel_id = channel_id or ""
        self.format = format
        self._driver: Any = None

    @property
    def driver(self) -> Any:
        """Get the Mattermost driver (lazy loaded).

        Returns:
            The mattermostdriver Driver instance.

        Raises:
            NotificationError: If mattermostdriver is not installed.
        """
        if self._driver is None:
            try:
                from mattermostdriver import Driver
            except ImportError as e:
                raise NotificationError(
                    "mattermostdriver is not installed. "
                    "Install it with: pip install web-perfmonitor[mattermost]"
                ) from e

            # Parse server URL
            url = self.server_url.rstrip("/")
            if url.startswith("https://"):
                url = url[8:]
                scheme = "https"
            elif url.startswith("http://"):
                url = url[7:]
                scheme = "http"
            else:
                scheme = "https"

            self._driver = Driver(
                {
                    "url": url,
                    "token": self.token,
                    "scheme": scheme,
                    "port": 443 if scheme == "https" else 80,
                    "verify": True,
                }
            )
            self._driver.login()
            logger.debug(f"Connected to Mattermost server: {self.server_url}")

        return self._driver

    def send(
        self,
        profile: "PerformanceProfile",
        format: Optional[str] = None,
    ) -> None:
        """Send performance alert to Mattermost channel with zip attachment.

        Args:
            profile: The performance profile to send.
            format: Message format override ("markdown" or "text").
                   Uses instance format if not specified.

        Raises:
            NotificationError: If sending fails.
        """
        actual_format = format or self.format

        try:
            # Format message (brief summary for channel)
            message = self._format_brief_message(profile)

            # Generate zip report
            zip_bytes, zip_filename = self.generate_zip_report(profile)

            # Upload file first
            file_response = self.driver.files.upload_file(
                channel_id=self.channel_id,
                files={
                    "files": (zip_filename, zip_bytes, "application/zip")
                }
            )

            file_ids = [f["id"] for f in file_response.get("file_infos", [])]

            # Send message with file attachment
            self.driver.posts.create_post(
                {
                    "channel_id": self.channel_id,
                    "message": message,
                    "file_ids": file_ids,
                }
            )

            logger.info(
                f"Sent performance alert to Mattermost channel {self.channel_id}: "
                f"{profile.endpoint} (with zip attachment)"
            )

        except NotificationError:
            # Re-raise notification errors
            raise
        except Exception as e:
            error_msg = f"Failed to send Mattermost notification: {e}"
            logger.error(error_msg, exc_info=True)
            raise NotificationError(error_msg) from e

    def _format_brief_message(self, profile: "PerformanceProfile") -> str:
        """Format a brief message for the channel post.

        Args:
            profile: The performance profile.

        Returns:
            Brief markdown message.
        """
        return (
            f"### :warning: Performance Alert: `{profile.endpoint}`\n\n"
            f"| Field | Value |\n"
            f"|-------|-------|\n"
            f"| **Method** | {profile.method} |\n"
            f"| **Duration** | {profile.duration_seconds:.3f}s |\n"
            f"| **Timestamp** | {profile.timestamp.isoformat()} |\n\n"
            f"See attached zip file for detailed HTML and Markdown reports."
        )

    def validate_config(self) -> bool:
        """Validate the notifier configuration.

        Checks that server_url, token, and channel_id are provided.

        Returns:
            True if configuration is valid, False otherwise.
        """
        if not self.server_url:
            logger.warning("Mattermost server_url is not configured")
            return False

        if not self.token:
            logger.warning("Mattermost token is not configured")
            return False

        if not self.channel_id:
            logger.warning("Mattermost channel_id is not configured")
            return False

        return True

    def _format_markdown(self, profile: "PerformanceProfile") -> str:
        """Format message as Mattermost-style markdown.

        Args:
            profile: The performance profile.

        Returns:
            Markdown formatted message for Mattermost.
        """
        lines = [
            f"### :warning: Performance Alert: `{profile.endpoint}`",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Endpoint** | `{profile.endpoint}` |",
            f"| **Method** | {profile.method} |",
            f"| **Duration** | {profile.duration_seconds:.3f}s |",
            f"| **Timestamp** | {profile.timestamp.isoformat()} |",
            "",
        ]

        if profile.metadata:
            lines.append("**Request Details:**")
            for key, value in profile.metadata.items():
                lines.append(f"- {key}: `{value}`")
            lines.append("")

        # Add collapsed text report
        lines.append("<details>")
        lines.append("<summary>Performance Profile</summary>")
        lines.append("")
        lines.append("```")
        # Truncate long reports
        report = profile.text_report
        if len(report) > 3000:
            report = report[:3000] + "\n... (truncated)"
        lines.append(report)
        lines.append("```")
        lines.append("</details>")

        return "\n".join(lines)

    def _format_text(self, profile: "PerformanceProfile") -> str:
        """Format message as plain text.

        Args:
            profile: The performance profile.

        Returns:
            Plain text formatted message.
        """
        lines = [
            f"⚠️ PERFORMANCE ALERT: {profile.endpoint}",
            "",
            f"Endpoint: {profile.endpoint}",
            f"Method: {profile.method}",
            f"Duration: {profile.duration_seconds:.3f}s",
            f"Timestamp: {profile.timestamp.isoformat()}",
            "",
        ]

        if profile.metadata:
            lines.append("Request Details:")
            for key, value in profile.metadata.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        lines.append("Performance Profile:")
        lines.append("-" * 40)
        # Truncate long reports
        report = profile.text_report
        if len(report) > 2000:
            report = report[:2000] + "\n... (truncated)"
        lines.append(report)

        return "\n".join(lines)
