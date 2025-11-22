# 快速入门：Web 性能监控告警系统

**日期**: 2025-11-22
**预计时间**: 5 分钟

## 安装

```bash
pip install web-perfmonitor
```

如需 Mattermost 通知支持：
```bash
pip install web-perfmonitor[mattermost]
```

## 最简集成（3 行代码）

```python
from flask import Flask
from web_perfmonitor import PerformanceMiddleware

app = Flask(__name__)
PerformanceMiddleware(app)  # 就这么简单！

@app.route("/api/users")
def get_users():
    # 你的业务代码
    return {"users": [...]}

if __name__ == "__main__":
    app.run()
```

**效果**：
- 所有接口自动被监控
- 响应时间超过 1 秒时生成性能报告
- 报告保存在 `/tmp` 目录

## 自定义配置

### 方式 1：代码配置

```python
from web_perfmonitor import PerformanceMiddleware, MonitorConfig

config = MonitorConfig(
    threshold_seconds=0.5,      # 500ms 阈值
    alert_window_days=7,        # 7 天内同一接口不重复告警
    log_path="/var/log/myapp",  # 报告保存目录
    url_whitelist=["/api/*"],   # 只监控 /api/ 开头的接口
)

PerformanceMiddleware(app, config=config)
```

### 方式 2：环境变量

```bash
export PERF_THRESHOLD=0.5
export PERF_ALERT_WINDOW=7
export PERF_LOG_PATH=/var/log/myapp
export PERF_URL_WHITELIST="/api/*"
```

```python
from web_perfmonitor import PerformanceMiddleware, MonitorConfig

config = MonitorConfig.from_env()
PerformanceMiddleware(app, config=config)
```

## 配置通知渠道

**注意**：本地报告保存是自动且强制的。报告会以 HTML 和 Markdown 格式保存到 `log_path` 目录。

`notice_list` 仅用于配置**外部通知器**（如 Mattermost、Slack 等）：

### Mattermost 通知

```python
config = MonitorConfig(
    log_path="/var/log/myapp",  # 本地报告保存目录（强制）
    notice_list=[
        # 仅外部通知器
        {
            "type": "mattermost",
            "format": "markdown",
            "server_url": "https://mattermost.example.com",
            "token": "your-api-token",
            "channel_id": "your-channel-id"
        }
    ]
)

PerformanceMiddleware(app, config=config)
```

## 装饰器模式（监控特定函数）

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

### 白名单（只监控指定 URL）

```python
config = MonitorConfig(
    url_whitelist=[
        "/api/*",       # 监控所有 /api/ 开头的接口
        "/v1/users",    # 精确匹配
    ]
)
```

### 黑名单（排除指定 URL）

```python
config = MonitorConfig(
    url_blacklist=[
        "/health",      # 排除健康检查
        "/metrics",     # 排除监控端点
        "/static/*",    # 排除静态资源
    ]
)
```

**注意**：白名单和黑名单互斥，配置了白名单则黑名单不生效。

## 验证安装

创建测试文件 `test_monitor.py`：

```python
from flask import Flask
from web_perfmonitor import PerformanceMiddleware
import time

app = Flask(__name__)
PerformanceMiddleware(app, threshold_seconds=0.1)

@app.route("/slow")
def slow():
    time.sleep(0.2)  # 模拟慢接口
    return "OK"

@app.route("/fast")
def fast():
    return "OK"

if __name__ == "__main__":
    app.run(debug=True)
```

运行后访问：
- `http://localhost:5000/slow` - 触发告警（报告保存到 /tmp）
- `http://localhost:5000/fast` - 不触发告警

检查报告：
```bash
ls /tmp/*.html  # 查看生成的性能报告
```

## 完整配置参考

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| threshold_seconds | float | 1.0 | 性能阈值（秒） |
| alert_window_days | int | 10 | 告警去重窗口（天） |
| max_performance_overhead | float | 0.05 | 最大性能开销比例 |
| log_path | str | /tmp | 报告保存目录 |
| url_whitelist | List[str] | [] | URL 白名单 |
| url_blacklist | List[str] | [] | URL 黑名单 |
| notice_list | List[dict] | [] | 通知渠道配置 |
| notice_timeout_seconds | float | 30.0 | 通知超时时间 |
| notice_queue_size | int | 1000 | 通知队列大小 |
| graceful_shutdown_seconds | float | 5.0 | 优雅关闭等待时间 |

## 下一步

- [API 文档](./contracts/python-api.md) - 完整 API 参考
- [数据模型](./data-model.md) - 了解内部数据结构
- [技术研究](./research.md) - 了解设计决策
