"""Base notifier for performance notifications.

This module defines the abstract base class for notification implementations
(local file, Mattermost, etc.).
"""

import io
import logging
import re
import zipfile
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple, TYPE_CHECKING

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

    def _extract_request_data(self, profile: "PerformanceProfile") -> dict:
        """Extract request data from profile metadata.

        Args:
            profile: The performance profile.

        Returns:
            Dictionary containing extracted request data with keys:
                - url: Request URL
                - path: Request path
                - method: HTTP method
                - query_params: Query parameters dict
                - form_data: Form data dict
                - json_body: JSON body dict or other type
                - other_metadata: Other metadata excluding request params
        """
        if not profile.metadata:
            return {}

        url = profile.metadata.get("url", "")
        path = profile.metadata.get("path", profile.endpoint)
        method = profile.metadata.get("method", profile.method)

        query_params = profile.metadata.get("query_params")
        form_data = profile.metadata.get("form_data")
        json_body = profile.metadata.get("json_body")
        request_headers = profile.metadata.get("request_headers")

        # Extract other metadata (exclude special keys)
        exclude_keys = {"query_params", "form_data", "json_body", "query_string", "url", "path", "method", "request_headers"}
        other_metadata = {
            k: v for k, v in profile.metadata.items() if k not in exclude_keys
        }

        return {
            "url": url,
            "path": path,
            "method": method,
            "query_params": query_params,
            "form_data": form_data,
            "json_body": json_body,
            "request_headers": request_headers,
            "other_metadata": other_metadata,
        }

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

        # Extract request data
        request_data = self._extract_request_data(profile)

        if request_data:
            url = request_data["url"]
            path = request_data["path"]
            method = request_data["method"]
            query_params = request_data["query_params"]
            form_data = request_data["form_data"]
            json_body = request_data["json_body"]
            request_headers = request_data["request_headers"]
            other_metadata = request_data["other_metadata"]

            # Request Details section
            lines.append("### 请求详情")
            lines.append("")
            if url:
                lines.append(f"**URL**: {url}")
            lines.append(f"**路径**: {path}")
            lines.append(f"**请求方法**: {method}")
            lines.append("")

            # Request Headers section
            if request_headers:
                lines.append("### 请求头")
                lines.append("")
                for header_name, header_value in request_headers.items():
                    lines.append(f"- **{header_name}**: {header_value}")
                lines.append("")

            # Request Parameters section (detailed)
            if query_params or form_data or json_body:
                lines.append("### 请求参数")
                lines.append("")

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

            # Other metadata section
            if other_metadata:
                # Translate metadata keys to Chinese
                key_translations = {
                    "remote_addr": "客户端IP",
                    "user_agent": "用户代理",
                    "content_length": "内容长度",
                }

                lines.append("### 其他信息")
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

    def generate_zip_report(
        self,
        profile: "PerformanceProfile",
    ) -> Tuple[bytes, str]:
        """Generate a zip file containing HTML and Markdown reports.

        Creates a zip archive with both the HTML and Markdown versions
        of the performance report for attachment to external notifications.

        Args:
            profile: The performance profile.

        Returns:
            Tuple of (zip_bytes, filename) where zip_bytes is the zip file
            content as bytes and filename is the suggested filename.
        """
        # Generate filename base
        filename_base = self._generate_report_filename(profile)

        # Create zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add markdown report
            markdown_content = self._format_markdown(profile)
            zf.writestr(f"{filename_base}.md", markdown_content.encode("utf-8"))

            # Add HTML report
            html_content = self._generate_html_report(profile)
            zf.writestr(f"{filename_base}.html", html_content.encode("utf-8"))

        zip_bytes = zip_buffer.getvalue()
        zip_filename = f"{filename_base}.zip"

        logger.debug(f"Generated zip report: {zip_filename} ({len(zip_bytes)} bytes)")
        return zip_bytes, zip_filename

    def _generate_report_filename(self, profile: "PerformanceProfile") -> str:
        """Generate a base filename for reports.

        Args:
            profile: The performance profile.

        Returns:
            Base filename without extension.
        """
        # Strip HTTP method prefix from endpoint
        endpoint = profile.endpoint
        http_methods = ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS ")
        for method in http_methods:
            if endpoint.startswith(method):
                endpoint = endpoint[len(method):]
                break

        # Sanitize endpoint for filename
        sanitized = re.sub(r"[/\\?%*:|\"<>]", "_", endpoint)
        sanitized = re.sub(r"_+", "_", sanitized)
        sanitized = sanitized.strip("_")
        if len(sanitized) > 50:
            sanitized = sanitized[:50]
        sanitized = sanitized or "unknown"

        # Use short ID
        short_id = profile.id[:8]

        return f"perf_report_{sanitized}_{short_id}"

    def _generate_html_report(self, profile: "PerformanceProfile") -> str:
        """Generate full HTML report.

        Args:
            profile: The performance profile.

        Returns:
            HTML content string.
        """
        import html
        import json

        # Extract request data
        request_data = self._extract_request_data(profile)

        # Build request details section
        details_html = ""
        if request_data:
            url = request_data["url"]
            path = request_data["path"]
            method = request_data["method"]

            details_html = "<h3>请求详情</h3><ul>"
            if url:
                details_html += f"<li><strong>URL:</strong> {html.escape(url)}</li>"
            details_html += f"<li><strong>路径:</strong> {html.escape(path)}</li>"
            details_html += f"<li><strong>请求方法:</strong> {html.escape(method)}</li>"
            details_html += "</ul>"

        # Build request params section
        params_html = ""
        if request_data:
            query_params = request_data["query_params"]
            form_data = request_data["form_data"]
            json_body = request_data["json_body"]

            if query_params or form_data or json_body:
                params_html = "<h3>请求参数</h3>"

                if query_params:
                    params_html += """
                    <p><strong>URL 查询参数:</strong></p>
                    <pre style="background:#f5f5f5;padding:10px;border-radius:4px;">{}</pre>
                    """.format(html.escape(json.dumps(query_params, indent=2, ensure_ascii=False)))

                if form_data:
                    params_html += """
                    <p><strong>表单数据:</strong></p>
                    <pre style="background:#f5f5f5;padding:10px;border-radius:4px;">{}</pre>
                    """.format(html.escape(json.dumps(form_data, indent=2, ensure_ascii=False)))

                if json_body:
                    params_html += """
                    <p><strong>JSON 请求体:</strong></p>
                    <pre style="background:#f5f5f5;padding:10px;border-radius:4px;">{}</pre>
                    """.format(html.escape(json.dumps(json_body, indent=2, ensure_ascii=False)))

        # Build metadata section
        metadata_html = ""
        if request_data:
            other_metadata = request_data["other_metadata"]
            if other_metadata:
                metadata_html = "<h3>其他信息</h3><ul>"
                for key, value in other_metadata.items():
                    metadata_html += f"<li><strong>{html.escape(str(key))}:</strong> {html.escape(str(value))}</li>"
                metadata_html += "</ul>"

        # Use pyinstrument HTML if available
        profile_section = ""
        if profile.html_report:
            profile_section = profile.html_report
        else:
            profile_section = f"<pre>{html.escape(profile.text_report)}</pre>"

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Performance Report: {html.escape(profile.endpoint)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .alert-header {{
            background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .alert-header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        .info-table th, .info-table td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        .info-table th {{
            background-color: #f8f9fa;
            font-weight: 600;
            width: 150px;
        }}
        .duration {{
            font-size: 28px;
            font-weight: bold;
            color: #dc3545;
        }}
        pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 12px;
            line-height: 1.4;
        }}
        h3 {{
            color: #495057;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div class="alert-header">
        <h1>Performance Alert</h1>
    </div>

    <table class="info-table">
        <tr>
            <th>Endpoint</th>
            <td><code>{html.escape(profile.endpoint)}</code></td>
        </tr>
        <tr>
            <th>Method</th>
            <td>{html.escape(profile.method)}</td>
        </tr>
        <tr>
            <th>Duration</th>
            <td><span class="duration">{profile.duration_seconds:.3f}s</span></td>
        </tr>
        <tr>
            <th>Timestamp</th>
            <td>{profile.timestamp.isoformat()}</td>
        </tr>
        <tr>
            <th>Profile ID</th>
            <td><code>{profile.id}</code></td>
        </tr>
    </table>

    {details_html}
    {params_html}
    {metadata_html}

    <h3>Performance Profile</h3>
    {profile_section}

    <hr style="border:none;border-top:1px solid #eee;margin:30px 0;">
    <p style="color:#999;font-size:12px;">
        Generated by Web Performance Monitor
    </p>
</body>
</html>"""
