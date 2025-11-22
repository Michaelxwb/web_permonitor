# Web Performance Monitor

基于 pyinstrument 的轻量级 Python Web 框架性能监控库。

[![PyPI version](https://badge.fury.io/py/web-perfmonitor.svg)](https://badge.fury.io/py/web-perfmonitor)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 功能特性

- **零侵入式监控** - 无需修改应用代码即可添加性能监控
- **自动性能分析** - 当响应时间超过阈值时自动捕获详细调用栈
- **告警去重** - 可配置时间窗口，避免告警轰炸
- **多通知渠道** - 支持本地文件、Mattermost，可扩展自定义渠道
- **URL 过滤** - 支持白名单/黑名单模式控制监控范围
- **异步通知** - 非阻塞式通知发送
- **多框架支持** - 支持 Flask 和 FastAPI（包括 async/await），可扩展至 Django 等

## 安装

```bash
pip install web-perfmonitor
```

如需 FastAPI 支持：
```bash
pip install web-perfmonitor[fastapi]
```

如需 Mattermost 通知支持：
```bash
pip install web-perfmonitor[mattermost]
```

## 快速开始

### Flask（最小化配置）

```python
from flask import Flask
from web_perfmonitor import PerformanceMiddleware

app = Flask(__name__)
PerformanceMiddleware(app)  # 就这么简单！

@app.route("/api/users")
def get_users():
    # 你的业务逻辑
    return {"users": [...]}

if __name__ == "__main__":
    app.run()
```

### FastAPI（异步支持）

```python
from fastapi import FastAPI
from web_perfmonitor import PerformanceMiddleware

app = FastAPI()
PerformanceMiddleware(app)  # 自动检测 FastAPI

@app.get("/api/users")
async def get_users():
    # 你的异步业务逻辑
    return {"users": [...]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**效果说明：**
- 所有接口自动被监控
- 当响应时间超过 1 秒时生成性能报告
- 报告保存至 `/tmp` 目录
- 对于 FastAPI，异步函数的调用栈可被完整采集

### 自定义配置

```python
from web_perfmonitor import PerformanceMiddleware, MonitorConfig

config = MonitorConfig(
    threshold_seconds=0.5,      # 500ms 阈值
    alert_window_days=7,        # 7 天去重窗口
    log_path="/var/log/myapp",  # 报告保存目录
    url_whitelist=["/api/*"],   # 仅监控 /api/* 接口
)

PerformanceMiddleware(app, config=config)
```

### 环境变量配置

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

## 通知渠道

**注意：** 本地报告保存是自动且强制的。报告始终会以 HTML 和 Markdown 格式保存至 `log_path`。

`notice_list` 仅用于配置**外部通知器**（Mattermost、Email、Slack 等）。

**Zip 附件：** 所有外部通知器会自动附加一个包含 HTML 和 Markdown 报告的 zip 压缩包，便于离线查看和存档。

### Mattermost 通知

```python
config = MonitorConfig(
    log_path="/var/log/perf-reports",  # 本地报告保存位置（必须）
    notice_list=[
        # 仅配置外部通知器
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

### Email 邮件通知

```python
config = MonitorConfig(
    log_path="/var/log/perf-reports",
    notice_list=[
        {
            "type": "email",
            "format": "html",  # 或 "text"
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "username": "alerts@example.com",
            "password": "your-password",
            "sender": "alerts@example.com",
            "recipients": ["dev@example.com", "ops@example.com"],
            "use_tls": True,
            "subject_prefix": "[性能告警]"
        }
    ]
)
```

**邮件配置参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| smtp_host | str | - | SMTP 服务器地址（必填） |
| smtp_port | int | 587 | SMTP 服务器端口 |
| username | str | - | SMTP 认证用户名 |
| password | str | - | SMTP 认证密码 |
| sender | str | - | 发件人邮箱地址（必填） |
| recipients | List[str] | - | 收件人邮箱地址列表（必填） |
| use_tls | bool | True | 使用 STARTTLS 加密 |
| use_ssl | bool | False | 从连接开始使用 SSL/TLS |
| format | str | "html" | 邮件格式（"html" 或 "text"） |
| subject_prefix | str | "[Performance Alert]" | 邮件主题前缀 |

## 函数级性能分析

```python
from web_perfmonitor import profile

@profile()
def slow_operation():
    # 耗时操作
    time.sleep(2)

@profile(threshold=0.1)  # 自定义阈值
def critical_function():
    # 关键操作
    pass
```

## URL 过滤

### 白名单（仅监控指定 URL）

```python
config = MonitorConfig(
    url_whitelist=[
        "/api/*",       # 监控所有 /api/* 接口
        "/v1/users",    # 精确匹配
    ]
)
```

### 黑名单（排除指定 URL）

```python
config = MonitorConfig(
    url_blacklist=[
        "/health",      # 排除健康检查
        "/metrics",     # 排除指标接口
        "/static/*",    # 排除静态文件
    ]
)
```

**注意：** 白名单优先级高于黑名单。

## 配置参数参考

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| threshold_seconds | float | 1.0 | 性能阈值（秒） |
| alert_window_days | int | 10 | 告警去重窗口（天） |
| max_performance_overhead | float | 0.05 | 最大性能开销比率 |
| log_path | str | /tmp | 报告保存目录 |
| url_whitelist | List[str] | [] | URL 白名单模式 |
| url_blacklist | List[str] | [] | URL 黑名单模式 |
| notice_list | List[dict] | [] | 通知渠道配置 |
| notice_timeout_seconds | float | 30.0 | 通知超时时间 |
| notice_queue_size | int | 1000 | 通知队列大小 |
| graceful_shutdown_seconds | float | 5.0 | 优雅关闭超时时间 |

## 扩展开发

### 自定义通知器

```python
from web_perfmonitor.notifiers import BaseNotifier, register_notifier

@register_notifier("slack")
class SlackNotifier(BaseNotifier):
    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url

    def send(self, profile, format="markdown"):
        # 实现 Slack 通知逻辑
        ...

    def validate_config(self) -> bool:
        return bool(self.webhook_url)
```

### 自定义框架适配器

```python
from web_perfmonitor.core import FrameworkRegistry, BaseAdapter

@FrameworkRegistry.register("django")
class DjangoAdapter(BaseAdapter):
    # 实现 Django 特定适配器
    ...
```

## 环境要求

- Python 3.8+
- Flask 2.0+ 或 FastAPI 0.100+
- pyinstrument 4.0+

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

## 贡献

欢迎贡献代码！请随时提交 Pull Request。
