# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-22

### Added

- **Core Framework**
  - `PerformanceMiddleware` - Zero-intrusion middleware for Flask applications
  - `profile` decorator - Function-level performance monitoring
  - `MonitorConfig` - Configuration management with environment variable support
  - `PerformanceProfile` - Immutable data class for profiling results

- **Notification System**
  - `LocalNotifier` - Save reports to local filesystem (HTML, Markdown, Text)
  - `MattermostNotifier` - Send alerts to Mattermost channels
  - `BaseNotifier` - Extensible base class for custom notifiers
  - `register_notifier` - Decorator for registering custom notification channels

- **Alert Management**
  - `AlertManager` - Time-window based alert deduplication
  - JSON persistence for alert records

- **URL Filtering**
  - `UrlFilter` - Whitelist/blacklist pattern matching
  - fnmatch glob-style pattern support

- **Framework Abstraction**
  - `FrameworkRegistry` - Plugin architecture for framework support
  - `BaseAdapter` - Generic adapter interface
  - `BaseMiddleware` - Shared middleware functionality
  - `BaseDecorator` - Shared decorator functionality
  - `FlaskAdapter` - Flask-specific implementation

- **Configuration Options**
  - `threshold_seconds` - Performance threshold
  - `alert_window_days` - Deduplication window
  - `log_path` - Report output directory
  - `url_whitelist` / `url_blacklist` - URL filtering
  - `notice_list` - Multiple notification channels
  - `notice_timeout_seconds` - Notification timeout
  - `notice_queue_size` - Queue size limit
  - `graceful_shutdown_seconds` - Shutdown timeout

### Technical Details

- Based on pyinstrument for low-overhead sampling profiler
- Thread-safe alert management with file persistence
- Async notification execution (non-blocking)
- Zero intrusion principle - monitoring never affects application behavior
- Full type hints for IDE support

## [Unreleased]

### Planned

- Django framework support
- FastAPI framework support
- Prometheus metrics export
- Email notification channel
- Web dashboard for report viewing
