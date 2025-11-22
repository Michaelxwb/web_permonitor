"""Email notifier for performance alerts.

This module provides a notifier that sends performance alerts via email
using SMTP.
"""

import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, List, Optional, TYPE_CHECKING, Union

from ..exceptions import NotificationError
from . import register_notifier
from .base import BaseNotifier

if TYPE_CHECKING:
    from ..models import PerformanceProfile

logger = logging.getLogger(__name__)


@register_notifier("email")
class EmailNotifier(BaseNotifier):
    """Notifier that sends performance alerts via email.

    Uses SMTP to send HTML/text emails to configured recipients.

    Attributes:
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        username: SMTP authentication username.
        password: SMTP authentication password.
        sender: Sender email address.
        recipients: List of recipient email addresses.
        use_tls: Whether to use TLS encryption.
        use_ssl: Whether to use SSL encryption.
        format: Message format ("html" or "text").

    Example:
        notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="alerts@example.com",
            password="your-password",
            sender="alerts@example.com",
            recipients=["dev@example.com", "ops@example.com"],
            use_tls=True,
            format="html"
        )
        notifier.send(profile)
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sender: Optional[str] = None,
        recipients: Optional[Union[str, List[str]]] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        format: str = "html",
        subject_prefix: str = "[Performance Alert]",
        **kwargs: Any,
    ) -> None:
        """Initialize the email notifier.

        Args:
            smtp_host: SMTP server hostname.
            smtp_port: SMTP server port (default: 587 for TLS).
            username: SMTP authentication username.
            password: SMTP authentication password.
            sender: Sender email address.
            recipients: Single recipient or list of recipient email addresses.
            use_tls: Whether to use STARTTLS (default: True).
            use_ssl: Whether to use SSL/TLS from start (default: False).
            format: Message format ("html" or "text", default: "html").
            subject_prefix: Email subject prefix (default: "[Performance Alert]").
            **kwargs: Additional configuration options.
        """
        super().__init__(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            sender=sender,
            recipients=recipients,
            use_tls=use_tls,
            use_ssl=use_ssl,
            format=format,
            subject_prefix=subject_prefix,
            **kwargs,
        )
        self.smtp_host = smtp_host or ""
        self.smtp_port = smtp_port
        self.username = username or ""
        self.password = password or ""
        self.sender = sender or ""
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.format = format
        self.subject_prefix = subject_prefix

        # Handle recipients as string or list
        if isinstance(recipients, str):
            self.recipients = [r.strip() for r in recipients.split(",") if r.strip()]
        elif recipients:
            self.recipients = list(recipients)
        else:
            self.recipients = []

    def send(
        self,
        profile: "PerformanceProfile",
        format: Optional[str] = None,
    ) -> None:
        """Send performance alert via email with zip attachment.

        Args:
            profile: The performance profile to send.
            format: Message format override ("html" or "text").
                   Uses instance format if not specified.

        Raises:
            NotificationError: If sending fails.
        """
        actual_format = format or self.format

        try:
            # Create mixed message (for attachments)
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"{self.subject_prefix} {profile.endpoint} - {profile.duration_seconds:.3f}s"
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)

            # Create alternative part for text/html body
            body_part = MIMEMultipart("alternative")

            # Add text version (always include for fallback)
            text_content = self._format_brief_text(profile)
            body_part.attach(MIMEText(text_content, "plain", "utf-8"))

            # Add HTML version if requested
            if actual_format == "html":
                html_content = self._format_brief_html(profile)
                body_part.attach(MIMEText(html_content, "html", "utf-8"))

            msg.attach(body_part)

            # Generate and attach zip report
            zip_bytes, zip_filename = self.generate_zip_report(profile)
            zip_attachment = MIMEApplication(zip_bytes, _subtype="zip")
            zip_attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=zip_filename
            )
            msg.attach(zip_attachment)

            # Send email
            self._send_email(msg)

            logger.info(
                f"Sent performance alert email to {self.recipients}: "
                f"{profile.endpoint} (with zip attachment)"
            )

        except NotificationError:
            raise
        except Exception as e:
            error_msg = f"Failed to send email notification: {e}"
            logger.error(error_msg, exc_info=True)
            raise NotificationError(error_msg) from e

    def _send_email(self, msg: MIMEMultipart) -> None:
        """Send the email message via SMTP.

        Args:
            msg: The email message to send.

        Raises:
            NotificationError: If SMTP connection or sending fails.
        """
        try:
            if self.use_ssl:
                # SSL connection from the start
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, context=context
                ) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.sender, self.recipients, msg.as_string())
            else:
                # Plain connection, optionally with STARTTLS
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.sendmail(self.sender, self.recipients, msg.as_string())

        except smtplib.SMTPAuthenticationError as e:
            raise NotificationError(
                f"SMTP authentication failed: {e}"
            ) from e
        except smtplib.SMTPException as e:
            raise NotificationError(
                f"SMTP error: {e}"
            ) from e
        except ConnectionError as e:
            raise NotificationError(
                f"Failed to connect to SMTP server {self.smtp_host}:{self.smtp_port}: {e}"
            ) from e

    def validate_config(self) -> bool:
        """Validate the notifier configuration.

        Checks that required SMTP settings are provided.

        Returns:
            True if configuration is valid, False otherwise.
        """
        if not self.smtp_host:
            logger.warning("Email smtp_host is not configured")
            return False

        if not self.sender:
            logger.warning("Email sender is not configured")
            return False

        if not self.recipients:
            logger.warning("Email recipients is not configured")
            return False

        return True

    def _format_brief_html(self, profile: "PerformanceProfile") -> str:
        """Format brief HTML message for email body.

        Args:
            profile: The performance profile.

        Returns:
            Brief HTML formatted message.
        """
        import html

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
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
        .attachment-note {{
            background: #e8f4fd;
            border: 1px solid #b8daff;
            border-radius: 4px;
            padding: 15px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="alert-header">
        <h1>性能告警</h1>
    </div>

    <table class="info-table">
        <tr>
            <th>接口地址</th>
            <td><code>{html.escape(profile.endpoint)}</code></td>
        </tr>
        <tr>
            <th>请求方法</th>
            <td>{html.escape(profile.method)}</td>
        </tr>
        <tr>
            <th>响应时间</th>
            <td><span class="duration">{profile.duration_seconds:.3f}s</span></td>
        </tr>
        <tr>
            <th>触发时间</th>
            <td>{profile.timestamp.isoformat()}</td>
        </tr>
    </table>

    <div class="attachment-note">
        <strong>详细报告已附加</strong><br>
        请查看附件中的 zip 压缩包，包含完整的 HTML 和 Markdown 格式性能分析报告。
    </div>

    <hr style="border:none;border-top:1px solid #eee;margin:30px 0;">
    <p style="color:#999;font-size:12px;">
        此告警由 Web Performance Monitor 自动生成
    </p>
</body>
</html>
"""

    def _format_brief_text(self, profile: "PerformanceProfile") -> str:
        """Format brief text message for email body.

        Args:
            profile: The performance profile.

        Returns:
            Brief plain text formatted message.
        """
        lines = [
            "=" * 60,
            "性能告警",
            "=" * 60,
            "",
            f"接口地址: {profile.endpoint}",
            f"请求方法: {profile.method}",
            f"响应时间: {profile.duration_seconds:.3f}s",
            f"触发时间: {profile.timestamp.isoformat()}",
            "",
            "-" * 40,
            "详细报告已附加",
            "-" * 40,
            "请查看附件中的 zip 压缩包，",
            "包含完整的 HTML 和 Markdown 格式性能分析报告。",
            "",
            "=" * 60,
        ]

        return "\n".join(lines)
