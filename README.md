# Web Performance Monitor

A lightweight performance monitoring library for Python web frameworks based on pyinstrument.

[![PyPI version](https://badge.fury.io/py/web-perfmonitor.svg)](https://badge.fury.io/py/web-perfmonitor)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Zero-intrusion monitoring** - Add performance monitoring without modifying your application code
- **Automatic profiling** - Captures detailed call stacks when response time exceeds threshold
- **Alert deduplication** - Prevents alert fatigue with configurable time windows
- **Multiple notification channels** - Local files, Mattermost, and extensible for custom channels
- **URL filtering** - Whitelist/blacklist patterns to control what gets monitored
- **Async notifications** - Non-blocking notification delivery
- **Framework extensible** - Currently supports Flask, designed for easy extension to Django, FastAPI, etc.

## Installation

```bash
pip install web-perfmonitor
```

For Mattermost notification support:
```bash
pip install web-perfmonitor[mattermost]
```

## Quick Start

### Minimal Setup (3 Lines of Code)

```python
from flask import Flask
from web_perf_monitor import PerformanceMiddleware

app = Flask(__name__)
PerformanceMiddleware(app)  # That's it!

@app.route("/api/users")
def get_users():
    # Your business logic
    return {"users": [...]}

if __name__ == "__main__":
    app.run()
```

**What happens:**
- All endpoints are automatically monitored
- Performance reports are generated when response time exceeds 1 second
- Reports are saved to `/tmp` directory

### Custom Configuration

```python
from web_perf_monitor import PerformanceMiddleware, MonitorConfig

config = MonitorConfig(
    threshold_seconds=0.5,      # 500ms threshold
    alert_window_days=7,        # 7-day deduplication window
    log_path="/var/log/myapp",  # Report save directory
    url_whitelist=["/api/*"],   # Only monitor /api/* endpoints
)

PerformanceMiddleware(app, config=config)
```

### Environment Variables

```bash
export PERF_THRESHOLD=0.5
export PERF_ALERT_WINDOW=7
export PERF_LOG_PATH=/var/log/myapp
export PERF_URL_WHITELIST="/api/*"
```

```python
config = MonitorConfig.from_env()
PerformanceMiddleware(app, config=config)
```

## Notification Channels

**Note:** Local report saving is automatic and mandatory. Reports are always saved to `log_path` in both HTML and Markdown formats.

The `notice_list` is only for **external notifiers** (Mattermost, Email, Slack, etc.).

**Zip Attachment:** All external notifiers automatically attach a zip file containing both HTML and Markdown reports for convenient offline viewing and archiving.

### Mattermost Notifications

```python
config = MonitorConfig(
    log_path="/var/log/perf-reports",  # Local reports saved here (mandatory)
    notice_list=[
        # External notifiers only
        {
            "type": "mattermost",
            "format": "markdown",
            "server_url": "https://mattermost.example.com",
            "token": "your-api-token",
            "channel_id": "your-channel-id"
        }
    ]
)
```

### Email Notifications

```python
config = MonitorConfig(
    log_path="/var/log/perf-reports",
    notice_list=[
        {
            "type": "email",
            "format": "html",  # or "text"
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "username": "alerts@example.com",
            "password": "your-password",
            "sender": "alerts@example.com",
            "recipients": ["dev@example.com", "ops@example.com"],
            "use_tls": True,
            "subject_prefix": "[Perf Alert]"
        }
    ]
)
```

**Email Configuration Options:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| smtp_host | str | - | SMTP server hostname (required) |
| smtp_port | int | 587 | SMTP server port |
| username | str | - | SMTP authentication username |
| password | str | - | SMTP authentication password |
| sender | str | - | Sender email address (required) |
| recipients | List[str] | - | Recipient email addresses (required) |
| use_tls | bool | True | Use STARTTLS encryption |
| use_ssl | bool | False | Use SSL/TLS from connection start |
| format | str | "html" | Email format ("html" or "text") |
| subject_prefix | str | "[Performance Alert]" | Email subject prefix |

## Function-Level Profiling

```python
from web_perf_monitor import profile

@profile()
def slow_operation():
    # Time-consuming operation
    time.sleep(2)

@profile(threshold=0.1)  # Custom threshold
def critical_function():
    # Critical operation
    pass
```

## URL Filtering

### Whitelist (monitor only specified URLs)

```python
config = MonitorConfig(
    url_whitelist=[
        "/api/*",       # Monitor all /api/* endpoints
        "/v1/users",    # Exact match
    ]
)
```

### Blacklist (exclude specified URLs)

```python
config = MonitorConfig(
    url_blacklist=[
        "/health",      # Exclude health checks
        "/metrics",     # Exclude metrics endpoint
        "/static/*",    # Exclude static files
    ]
)
```

**Note:** Whitelist takes precedence over blacklist.

## Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| threshold_seconds | float | 1.0 | Performance threshold (seconds) |
| alert_window_days | int | 10 | Alert deduplication window (days) |
| max_performance_overhead | float | 0.05 | Maximum performance overhead ratio |
| log_path | str | /tmp | Report save directory |
| url_whitelist | List[str] | [] | URL whitelist patterns |
| url_blacklist | List[str] | [] | URL blacklist patterns |
| notice_list | List[dict] | [] | Notification channel configs |
| notice_timeout_seconds | float | 30.0 | Notification timeout |
| notice_queue_size | int | 1000 | Notification queue size |
| graceful_shutdown_seconds | float | 5.0 | Graceful shutdown timeout |

## Extending

### Custom Notifier

```python
from web_perf_monitor.notifiers import BaseNotifier, register_notifier

@register_notifier("slack")
class SlackNotifier(BaseNotifier):
    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url

    def send(self, profile, format="markdown"):
        # Implement Slack notification
        ...

    def validate_config(self) -> bool:
        return bool(self.webhook_url)
```

### Custom Framework Adapter

```python
from web_perf_monitor.core import FrameworkRegistry, BaseAdapter

@FrameworkRegistry.register("django")
class DjangoAdapter(BaseAdapter):
    # Implement Django-specific adapter
    ...
```

## Requirements

- Python 3.8+
- Flask 2.0+
- pyinstrument 4.0+

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
