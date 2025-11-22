# 技术研究：Web 性能监控告警系统

**日期**: 2025-11-22
**关联计划**: [plan.md](./plan.md)

## 研究概述

本文档记录了 Web 性能监控系统技术选型和设计决策的研究过程（首期支持 Flask，架构支持扩展至其他框架）。

---

## 1. 性能分析工具选型

### 决策：pyinstrument

**选择理由**:
- 采样式分析器，开销极低（< 1% 通常情况）
- 专为 Python Web 应用设计
- 输出格式丰富（HTML、文本、JSON）
- 无需修改被分析代码
- 支持异步代码分析
- 活跃维护，社区支持良好

**考虑过的替代方案**:

| 工具 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| cProfile | 标准库，无额外依赖 | 追踪式，开销大 | 性能开销不符合 < 5% 要求 |
| line_profiler | 行级精度 | 需要装饰器标记 | 入侵性强，不符合零入侵原则 |
| yappi | 多线程支持好 | 追踪式，开销大 | 性能开销不符合要求 |
| py-spy | 进程外采样 | 需要特权运行 | 部署复杂度高 |

**pyinstrument 使用模式**:
```python
from pyinstrument import Profiler

profiler = Profiler()
profiler.start()
# ... 被监控代码 ...
profiler.stop()
output_html = profiler.output_html()
output_text = profiler.output_text()
```

---

## 2. Flask 中间件实现模式

### 决策：WSGI 中间件 + before/after_request 组合

**选择理由**:
- WSGI 中间件提供最外层包装，确保捕获完整请求周期
- before/after_request 钩子用于精确计时
- 不修改 Flask 核心行为，符合零入侵原则
- 兼容所有 Flask 扩展

**实现方案**:
```python
class PerformanceMiddleware:
    def __init__(self, app: Flask, config: MonitorConfig):
        self.wsgi_app = app.wsgi_app
        app.wsgi_app = self

        @app.before_request
        def start_profiling():
            if should_profile(request.path):
                g.profiler = Profiler()
                g.profiler.start()

        @app.after_request
        def stop_profiling(response):
            if hasattr(g, 'profiler'):
                g.profiler.stop()
                # 异步处理报告
            return response  # 不修改响应
```

**考虑过的替代方案**:

| 方案 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| 纯 WSGI 中间件 | 最底层控制 | 无法访问 Flask 上下文 | 无法获取路由信息 |
| 蓝图钩子 | 细粒度控制 | 需要每个蓝图注册 | 入侵性强 |
| Flask-Profiler 扩展 | 现成方案 | 功能固定，不可定制 | 不满足自定义需求 |

---

## 3. 异步通知执行策略

### 决策：ThreadPoolExecutor + 后台线程

**选择理由**:
- Python 3.8+ 内置，无额外依赖
- 并行执行多个通知渠道
- 超时控制通过 Future.result(timeout=) 实现
- 不阻塞主请求线程
- 优雅关闭支持

**实现方案**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

class NotificationExecutor:
    def __init__(self, max_workers: int = 10, timeout: float = 30):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.timeout = timeout
        self.queue = Queue(maxsize=1000)
        self._start_worker()

    def submit(self, task: NotificationTask):
        self.queue.put_nowait(task)  # 非阻塞

    def _worker(self):
        while True:
            task = self.queue.get()
            futures = [
                self.executor.submit(notifier.send, task.report)
                for notifier in task.notifiers
            ]
            for future in as_completed(futures, timeout=self.timeout):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Notification failed: {e}")
```

**考虑过的替代方案**:

| 方案 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| asyncio | 原生协程支持 | Flask 同步为主 | 增加复杂度 |
| Celery | 功能强大 | 需要消息队列 | 依赖过重 |
| APScheduler | 调度灵活 | 非即时执行 | 不适合实时通知 |
| 简单线程 | 最简单 | 无并行控制 | 无法并行多渠道 |

---

## 4. 告警去重存储

### 决策：本地 JSON 文件 + 内存缓存

**选择理由**:
- 无外部依赖，符合易集成原则
- 重启后状态可恢复
- 适合中小规模应用
- 实现简单，易于维护

**实现方案**:
```python
@dataclass
class AlertRecord:
    endpoint: str
    last_alert_time: datetime
    alert_count: int

class AlertDeduplicator:
    def __init__(self, storage_path: str, window_days: int = 10):
        self.storage_path = Path(storage_path) / "alerts.json"
        self.window = timedelta(days=window_days)
        self.cache: Dict[str, AlertRecord] = self._load()

    def should_alert(self, endpoint: str) -> bool:
        record = self.cache.get(endpoint)
        if not record:
            return True
        return datetime.now() - record.last_alert_time > self.window
```

**考虑过的替代方案**:

| 方案 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| SQLite | 结构化存储 | 增加依赖 | 过度设计 |
| Redis | 高性能，TTL 支持 | 需要外部服务 | 违反易集成原则 |
| 纯内存 | 最简单 | 重启丢失 | 不可接受 |

---

## 5. URL 过滤匹配算法

### 决策：fnmatch 风格通配符

**选择理由**:
- Python 标准库 fnmatch 支持
- 用户友好的通配符语法（`*` 匹配任意字符）
- 性能良好，O(n) 复杂度
- 易于理解和配置

**实现方案**:
```python
import fnmatch

class UrlFilter:
    def __init__(self, whitelist: List[str], blacklist: List[str]):
        self.whitelist = whitelist
        self.blacklist = blacklist

    def should_monitor(self, path: str) -> bool:
        # 白名单优先
        if self.whitelist:
            return any(fnmatch.fnmatch(path, p) for p in self.whitelist)
        # 黑名单排除
        if self.blacklist:
            return not any(fnmatch.fnmatch(path, p) for p in self.blacklist)
        return True  # 默认监控所有
```

**匹配规则**:
- 精确匹配：`/api/users` 仅匹配 `/api/users`
- 前缀通配：`/api/*` 匹配 `/api/users`、`/api/orders` 等
- 任意通配：`*/health` 匹配 `/v1/health`、`/v2/health` 等

---

## 6. 配置管理策略

### 决策：dataclass + 环境变量 + 字典合并

**选择理由**:
- dataclass 提供类型安全和默认值
- 环境变量支持 12-factor 应用
- 字典合并支持运行时配置
- 无需额外配置库

**实现方案**:
```python
import os
from dataclasses import dataclass, field

@dataclass
class MonitorConfig:
    threshold_seconds: float = 1.0
    alert_window_days: int = 10
    max_performance_overhead: float = 0.05
    log_path: str = "/tmp"
    url_whitelist: List[str] = field(default_factory=list)
    url_blacklist: List[str] = field(default_factory=list)
    notice_list: List[dict] = field(default_factory=list)
    notice_timeout_seconds: float = 30.0
    notice_queue_size: int = 1000
    graceful_shutdown_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        return cls(
            threshold_seconds=float(os.getenv("PERF_THRESHOLD", "1.0")),
            # ... 其他字段
        )
```

---

## 7. Mattermost 集成

### 决策：mattermostdriver 官方库

**选择理由**:
- 官方支持的 Python 客户端
- 完整 API 覆盖
- 活跃维护
- 支持 Token 认证

**实现方案**:
```python
from mattermostdriver import Driver

class MattermostNotifier(BaseNotifier):
    def __init__(self, server_url: str, token: str, channel_id: str):
        self.driver = Driver({
            'url': server_url,
            'token': token,
            'scheme': 'https',
            'port': 443
        })
        self.channel_id = channel_id

    def send(self, report: PerformanceProfile, format: str = "markdown"):
        message = self._format_message(report, format)
        self.driver.posts.create_post({
            'channel_id': self.channel_id,
            'message': message
        })
```

---

## 8. Web 框架抽象架构

### 决策：适配器模式 + 抽象基类 + 框架注册

**选择理由**:
- 核心逻辑与框架解耦，便于扩展新框架
- 统一的接口定义，保证各框架行为一致
- 注册机制支持运行时框架发现
- 符合开闭原则（OCP）

**架构分层**:

```
┌─────────────────────────────────────────────────────────┐
│                    用户代码层                            │
│  PerformanceMiddleware(app) / @profile()               │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    框架适配层                            │
│  FlaskAdapter / DjangoAdapter / ...                    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    核心抽象层                            │
│  BaseAdapter / BaseMiddleware / BaseDecorator          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    基础设施层                            │
│  Profiler / AlertDeduplicator / NotificationExecutor   │
└─────────────────────────────────────────────────────────┘
```

**核心抽象定义**:

```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Callable, Any

# 泛型应用类型
AppType = TypeVar("AppType")
RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")

class BaseAdapter(ABC, Generic[AppType, RequestType, ResponseType]):
    """框架适配器抽象基类"""

    @property
    @abstractmethod
    def framework_name(self) -> str:
        """框架名称，用于日志和调试"""
        pass

    @abstractmethod
    def get_request_path(self, request: RequestType) -> str:
        """从请求对象获取路径"""
        pass

    @abstractmethod
    def get_request_method(self, request: RequestType) -> str:
        """从请求对象获取 HTTP 方法"""
        pass

    @abstractmethod
    def get_request_metadata(self, request: RequestType) -> dict:
        """从请求对象获取元数据"""
        pass

    @abstractmethod
    def create_middleware(self, app: AppType, config: MonitorConfig) -> Any:
        """创建框架特定的中间件"""
        pass

    @abstractmethod
    def create_decorator(self, config: MonitorConfig) -> Callable:
        """创建框架特定的装饰器"""
        pass


class BaseMiddleware(ABC):
    """中间件抽象基类"""

    def __init__(self, config: MonitorConfig, adapter: BaseAdapter):
        self.config = config
        self.adapter = adapter
        self.profiler_manager = ProfilerManager(config)
        self.alert_deduplicator = AlertDeduplicator(config)
        self.executor = NotificationExecutor(config)

    @abstractmethod
    def install(self, app: Any) -> None:
        """安装中间件到应用"""
        pass

    def should_profile(self, path: str) -> bool:
        """判断是否需要监控"""
        return self.config.url_filter.should_monitor(path)

    def process_profile(self, profile: PerformanceProfile) -> None:
        """处理性能分析结果（通用逻辑）"""
        if profile.duration_seconds > self.config.threshold_seconds:
            if self.alert_deduplicator.should_alert(profile.endpoint):
                self.executor.submit(NotificationTask(profile))


class BaseDecorator(ABC):
    """装饰器抽象基类"""

    def __init__(self, config: MonitorConfig, adapter: BaseAdapter):
        self.config = config
        self.adapter = adapter

    @abstractmethod
    def __call__(self, func: Callable) -> Callable:
        """装饰函数"""
        pass
```

**Flask 适配器实现**:

```python
from flask import Flask, request, g, Response

@FrameworkRegistry.register("flask")
class FlaskAdapter(BaseAdapter[Flask, "LocalProxy", Response]):

    @property
    def framework_name(self) -> str:
        return "Flask"

    def get_request_path(self, request) -> str:
        return request.path

    def get_request_method(self, request) -> str:
        return request.method

    def get_request_metadata(self, request) -> dict:
        return {
            "query_params": dict(request.args),
            "user_agent": request.user_agent.string,
        }

    def create_middleware(self, app: Flask, config: MonitorConfig):
        return FlaskMiddleware(config, self).install(app)

    def create_decorator(self, config: MonitorConfig):
        return FlaskProfileDecorator(config, self)


class FlaskMiddleware(BaseMiddleware):
    """Flask 中间件实现"""

    def install(self, app: Flask) -> None:
        @app.before_request
        def _before():
            if self.should_profile(request.path):
                g._perf_profiler = Profiler()
                g._perf_profiler.start()

        @app.after_request
        def _after(response: Response) -> Response:
            if hasattr(g, '_perf_profiler'):
                g._perf_profiler.stop()
                profile = self._create_profile(g._perf_profiler)
                self.process_profile(profile)
            return response  # 不修改响应
```

**Django 适配器示例（后续扩展）**:

```python
# frameworks/django/adapter.py（未来实现）

from django.http import HttpRequest, HttpResponse

@FrameworkRegistry.register("django")
class DjangoAdapter(BaseAdapter[None, HttpRequest, HttpResponse]):

    @property
    def framework_name(self) -> str:
        return "Django"

    def get_request_path(self, request: HttpRequest) -> str:
        return request.path

    def get_request_method(self, request: HttpRequest) -> str:
        return request.method

    def create_middleware(self, app, config: MonitorConfig):
        # Django 使用 MIDDLEWARE 设置，返回中间件类
        return DjangoMiddleware

    def create_decorator(self, config: MonitorConfig):
        return DjangoProfileDecorator(config, self)


class DjangoMiddleware(BaseMiddleware):
    """Django 中间件实现"""

    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(MonitorConfig.from_env(), DjangoAdapter())

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self.should_profile(request.path):
            profiler = Profiler()
            profiler.start()

        response = self.get_response(request)

        if profiler:
            profiler.stop()
            profile = self._create_profile(profiler, request)
            self.process_profile(profile)

        return response
```

**框架注册机制**:

```python
class FrameworkRegistry:
    """框架注册器"""
    _adapters: Dict[str, Type[BaseAdapter]] = {}

    @classmethod
    def register(cls, name: str):
        """注册框架适配器"""
        def decorator(adapter_cls: Type[BaseAdapter]):
            cls._adapters[name] = adapter_cls
            return adapter_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> Type[BaseAdapter]:
        """获取框架适配器"""
        if name not in cls._adapters:
            raise ValueError(f"Unknown framework: {name}")
        return cls._adapters[name]

    @classmethod
    def auto_detect(cls, app: Any) -> BaseAdapter:
        """自动检测框架类型"""
        app_type = type(app).__module__
        if "flask" in app_type:
            return cls._adapters["flask"]()
        elif "django" in app_type:
            return cls._adapters["django"]()
        raise ValueError(f"Cannot detect framework for {app_type}")
```

**考虑过的替代方案**:

| 方案 | 优点 | 缺点 | 排除原因 |
|------|------|------|----------|
| 条件分支 | 实现简单 | 难以扩展 | 违反开闭原则 |
| 多继承 | 代码复用 | 菱形继承问题 | 复杂度高 |
| 组合模式 | 灵活 | 接口不统一 | 难以保证一致性 |

---

## 9. 通知器扩展架构

### 决策：抽象基类 + 注册模式

**选择理由**:
- 清晰的接口定义
- 易于扩展新通知渠道
- 类型安全
- 支持运行时注册

**实现方案**:
```python
from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    def send(self, report: PerformanceProfile, format: str) -> None:
        """发送通知"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """验证配置有效性"""
        pass

class NotifierRegistry:
    _notifiers: Dict[str, Type[BaseNotifier]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(notifier_cls: Type[BaseNotifier]):
            cls._notifiers[name] = notifier_cls
            return notifier_cls
        return decorator

@NotifierRegistry.register("local")
class LocalNotifier(BaseNotifier):
    ...

@NotifierRegistry.register("mattermost")
class MattermostNotifier(BaseNotifier):
    ...
```

---

## 9. PyPI 打包策略

### 决策：pyproject.toml + setuptools

**选择理由**:
- 现代 Python 打包标准（PEP 517/518）
- 单一配置文件
- 支持所有必要元数据
- 广泛工具支持

**配置示例**:
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "web-perf-monitor"
version = "0.1.0"
description = "Zero-intrusion performance monitoring for Python web frameworks"
requires-python = ">=3.8"
dependencies = [
    "Flask>=2.0.0",
    "pyinstrument>=4.0.0",
]

[project.optional-dependencies]
mattermost = ["mattermostdriver>=7.0.0"]

[tool.mypy]
strict = true
```

---

## 总结

所有技术决策均符合项目宪章原则：

| 决策领域 | 选择 | 符合原则 |
|----------|------|----------|
| 性能分析 | pyinstrument | II. 性能开销限制 |
| 中间件模式 | WSGI + 钩子 | I. 零入侵原则 |
| 异步执行 | ThreadPoolExecutor | II. 性能开销限制 |
| 告警存储 | JSON 文件 | IV. 易集成原则 |
| URL 过滤 | fnmatch | IV. 易集成原则 |
| 配置管理 | dataclass + 环境变量 | IV. 易集成原则 |
| **框架抽象** | **适配器模式 + 注册** | **FR-023 可扩展性** |
| 通知架构 | 抽象基类 + 注册 | FR-024 可扩展性 |
| 打包方式 | pyproject.toml | V. PyPI 发布标准 |

### 扩展新框架指南

要支持新的 Web 框架（如 Django），需要：

1. 在 `frameworks/` 下创建新目录（如 `django/`）
2. 实现 `BaseAdapter` 子类，定义框架特定的请求/响应处理
3. 实现 `BaseMiddleware` 子类，利用框架的中间件机制
4. 实现 `BaseDecorator` 子类（可选）
5. 使用 `@FrameworkRegistry.register("django")` 注册
6. 添加对应的单元测试和集成测试
