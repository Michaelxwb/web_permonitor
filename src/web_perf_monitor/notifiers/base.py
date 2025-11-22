"""Base notifier for performance notifications.

This module defines the abstract base class for notification implementations
(local file, Mattermost, etc.).
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import PerformanceProfile

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """Abstract base class for notification implementations.

    Provides the interface for sending performance alerts through various
    channels (local files, Mattermost, Slack, etc.).

    Subclasses must implement:
        - send(): Send the notification
        - validate_config(): Validate the notifier configuration

    Example:
        @register_notifier("slack")
        class SlackNotifier(BaseNotifier):
            def __init__(self, webhook_url: str, **kwargs):
                super().__init__(**kwargs)
                self.webhook_url = webhook_url

            def send(self, profile, format="markdown"):
                # Send to Slack
                ...

            def validate_config(self) -> bool:
                return bool(self.webhook_url)
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the notifier.

        Args:
            **kwargs: Notifier-specific configuration options.
        """
        self._config = kwargs

    @property
    def config(self) -> Dict[str, Any]:
        """Get the notifier configuration.

        Returns:
            Dictionary with configuration options.
        """
        return self._config

    @abstractmethod
    def send(
        self,
        profile: "PerformanceProfile",
        format: str = "markdown",
    ) -> None:
        """Send a performance notification.

        Args:
            profile: The performance profile to send.
            format: Message format ("markdown" or "text").

        Raises:
            NotificationError: If sending fails.
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the notifier configuration.

        Checks that all required configuration options are present
        and valid.

        Returns:
            True if configuration is valid, False otherwise.
        """
        pass

    def format_message(
        self,
        profile: "PerformanceProfile",
        format: str = "markdown",
    ) -> str:
        """Format the notification message.

        Default implementation provides a basic message format.
        Subclasses can override for custom formatting.

        Args:
            profile: The performance profile.
            format: Message format ("markdown" or "text").

        Returns:
            Formatted message string.
        """
        if format == "markdown":
            return self._format_markdown(profile)
        return self._format_text(profile)

    def _format_markdown(self, profile: "PerformanceProfile") -> str:
        """Format message as markdown.

        Args:
            profile: The performance profile.

        Returns:
            Markdown formatted message.
        """
        import json

        lines = [
            f"## 性能告警: {profile.endpoint}",
            "",
            f"**请求方法**: {profile.method}",
            f"**响应时间**: {profile.duration_seconds:.3f}s",
            f"**触发时间**: {profile.timestamp.isoformat()}",
            "",
        ]

        if profile.metadata:
            # Extract request parameters for special formatting
            query_params = profile.metadata.get("query_params")
            form_data = profile.metadata.get("form_data")
            json_body = profile.metadata.get("json_body")

            # Request Parameters section
            if query_params or form_data or json_body:
                lines.append("### 请求参数")

                if query_params:
                    lines.append("**URL 查询参数:**")
                    lines.append("```json")
                    lines.append(json.dumps(query_params, indent=2, ensure_ascii=False))
                    lines.append("```")
                    lines.append("")

                if form_data:
                    lines.append("**表单数据:**")
                    lines.append("```json")
                    lines.append(json.dumps(form_data, indent=2, ensure_ascii=False))
                    lines.append("```")
                    lines.append("")

                if json_body:
                    lines.append("**JSON 请求体:**")
                    lines.append("```json")
                    lines.append(json.dumps(json_body, indent=2, ensure_ascii=False))
                    lines.append("```")
                    lines.append("")

            # Other metadata (exclude special keys)
            exclude_keys = {"query_params", "form_data", "json_body", "query_string"}
            other_metadata = {
                k: v for k, v in profile.metadata.items() if k not in exclude_keys
            }

            # Translate metadata keys to Chinese
            key_translations = {
                "url": "请求URL",
                "path": "请求路径",
                "method": "请求方法",
                "remote_addr": "客户端IP",
                "user_agent": "用户代理",
                "content_length": "内容长度",
            }

            if other_metadata:
                lines.append("### 请求信息")
                for key, value in other_metadata.items():
                    display_key = key_translations.get(key, key)
                    lines.append(f"- **{display_key}**: {value}")
                lines.append("")

        lines.append("### 性能分析报告")
        lines.append("```")
        lines.append(profile.text_report)
        lines.append("```")

        return "\n".join(lines)

    def _format_text(self, profile: "PerformanceProfile") -> str:
        """Format message as plain text.

        Args:
            profile: The performance profile.

        Returns:
            Plain text formatted message.
        """
        lines = [
            f"Performance Alert: {profile.endpoint}",
            f"Method: {profile.method}",
            f"Duration: {profile.duration_seconds:.3f}s",
            f"Timestamp: {profile.timestamp.isoformat()}",
            "",
        ]

        if profile.metadata:
            lines.append("Metadata:")
            for key, value in profile.metadata.items():
                lines.append(f"  {key}: {value}")
            lines.append("")

        lines.append("Report:")
        lines.append("-" * 40)
        lines.append(profile.text_report)

        return "\n".join(lines)
