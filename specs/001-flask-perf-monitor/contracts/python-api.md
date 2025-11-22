# Python API 契约：Web 性能监控告警系统

**日期**: 2025-11-22
**关联计划**: [plan.md](../plan.md)

## 公共 API

### 模块入口

```python
from web_perf_monitor import (
    # 核心组件
    PerformanceMiddleware,
    profile,

    # 配置
    MonitorConfig,

    # 类型（可选导入）
    PerformanceProfile,
    NotificationConfig,
)

# 框架扩展接口（用于实现新框架支持）
from web_perf_monitor.core import (
    FrameworkRegistry,
    BaseAdapter,
    BaseMiddleware,
    BaseDecorator,
)

# 通知器扩展接口
from web_perf_monitor.notifiers import (
    BaseNotifier,
    register_notifier,
)
```

---

## 1. PerformanceMiddleware（性能中间件）

Web 应用性能监控中间件（当前支持 Flask，可扩展至其他框架）。

### 构造函数

```python
class PerformanceMiddleware:
    def __init__(
        self,
        app: Flask,
        config: Optional[MonitorConfig] = None,
        **kwargs
    ) -> None:
        """
        初始化性能监控中间件。

        Args:
            app: Flask 应用实例
            config: 监控配置，None 时使用默认值或环境变量
            **kwargs: 快捷配置参数，会覆盖 config 中的对应值

        Example:
            # 方式 1：使用默认配置
            PerformanceMiddleware(app)

            # 方式 2：使用配置对象
            config = MonitorConfig(threshold_seconds=2.0)
            PerformanceMiddleware(app, config=config)

            # 方式 3：使用快捷参数
            PerformanceMiddleware(app, threshold_seconds=2.0)
        """
```

### 方法

```python
def shutdown(self, timeout: Optional[float] = None) -> None:
    """
    优雅关闭中间件，等待未完成的通知任务。

    Args:
        timeout: 等待超时时间（秒），None 使用配置值
    """
```

---

## 2. profile 装饰器

函数级性能监控装饰器。

### 签名

```python
def profile(
    threshold: Optional[float] = None,
    name: Optional[str] = None,
) -> Callable[[F], F]:
    """
    装饰器：监控函数性能。

    Args:
        threshold: 阈值（秒），None 使用全局配置
        name: 自定义名称，None 使用函数名

    Returns:
        装饰后的函数，保持原始签名

    Example:
        @profile()
        def slow_function():
            ...

        @profile(threshold=0.5, name="critical_operation")
        def another_function():
            ...
    """
```

### 行为约定

- 装饰后函数返回值与原函数完全一致
- 装饰后函数异常行为与原函数完全一致
- 性能采集在后台执行，不阻塞函数返回
- 采集失败不影响函数执行

---

## 3. MonitorConfig（监控配置）

### 构造函数

```python
@dataclass
class MonitorConfig:
    threshold_seconds: float = 1.0
    alert_window_days: int = 10
    max_performance_overhead: float = 0.05
    log_path: str = "/tmp"
    url_whitelist: List[str] = field(default_factory=list)
    url_blacklist: List[str] = field(default_factory=list)
    notice_list: List[Dict[str, Any]] = field(default_factory=list)
    notice_timeout_seconds: float = 30.0
    notice_queue_size: int = 1000
    graceful_shutdown_seconds: float = 5.0
```

### 类方法

```python
@classmethod
def from_env(cls) -> "MonitorConfig":
    """
    从环境变量创建配置。

    环境变量映射：
        PERF_THRESHOLD -> threshold_seconds
        PERF_ALERT_WINDOW -> alert_window_days
        PERF_MAX_OVERHEAD -> max_performance_overhead
        PERF_LOG_PATH -> log_path
        PERF_URL_WHITELIST -> url_whitelist (逗号分隔)
        PERF_URL_BLACKLIST -> url_blacklist (逗号分隔)
        PERF_NOTICE_TIMEOUT -> notice_timeout_seconds
        PERF_NOTICE_QUEUE_SIZE -> notice_queue_size
        PERF_SHUTDOWN_TIMEOUT -> graceful_shutdown_seconds

    Returns:
        MonitorConfig 实例
    """

@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "MonitorConfig":
    """
    从字典创建配置。

    Args:
        data: 配置字典

    Returns:
        MonitorConfig 实例
    """
```

---

## 4. 通知渠道配置

### Local 通知

```python
{
    "type": "local",
    "format": "markdown",  # 或 "text"
    "output_dir": "/var/log/perf-reports"  # 可选，默认使用 log_path
}
```

### Mattermost 通知

```python
{
    "type": "mattermost",
    "format": "markdown",  # 或 "text"
    "server_url": "https://mattermost.example.com",
    "token": "your-api-token",
    "channel_id": "channel-id-here"
}
```

---

## 5. PerformanceProfile（性能分析结果）

只读数据类，表示一次性能采集结果。

```python
@dataclass(frozen=True)
class PerformanceProfile:
    id: str
    endpoint: str
    method: str
    duration_seconds: float
    timestamp: datetime
    html_report: str
    text_report: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
```

---

## 6. 框架扩展接口

### FrameworkRegistry（框架注册器）

用于注册和管理框架适配器。

```python
from web_perf_monitor.core import FrameworkRegistry, BaseAdapter

class FrameworkRegistry:
    @classmethod
    def register(cls, name: str) -> Callable[[Type[BaseAdapter]], Type[BaseAdapter]]:
        """
        装饰器：注册框架适配器。

        Args:
            name: 框架名称（如 "flask", "django"）

        Example:
            @FrameworkRegistry.register("flask")
            class FlaskAdapter(BaseAdapter):
                ...
        """

    @classmethod
    def get(cls, name: str) -> Type[BaseAdapter]:
        """
        获取指定框架的适配器类。

        Args:
            name: 框架名称

        Returns:
            适配器类

        Raises:
            KeyError: 框架未注册
        """

    @classmethod
    def list_frameworks(cls) -> List[str]:
        """列出所有已注册的框架名称"""

    @classmethod
    def auto_detect(cls, app: Any) -> Optional[BaseAdapter]:
        """
        自动检测应用类型并返回对应的适配器实例。

        Args:
            app: 应用实例

        Returns:
            适配器实例，无法检测时返回 None
        """
```

---

### BaseAdapter（框架适配器基类）

用于实现新框架的适配器。

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Callable, Any

AppType = TypeVar("AppType")
RequestType = TypeVar("RequestType")
ResponseType = TypeVar("ResponseType")

class BaseAdapter(ABC, Generic[AppType, RequestType, ResponseType]):
    """
    框架适配器抽象基类。

    泛型参数:
        AppType: 框架应用类型
        RequestType: 请求对象类型
        ResponseType: 响应对象类型
    """

    @abstractmethod
    def get_request_path(self, request: RequestType) -> str:
        """从请求对象中提取请求路径"""

    @abstractmethod
    def get_request_method(self, request: RequestType) -> str:
        """从请求对象中提取 HTTP 方法"""

    @abstractmethod
    def create_middleware(
        self, app: AppType, config: "MonitorConfig"
    ) -> "BaseMiddleware":
        """
        创建框架特定的中间件实例。

        Args:
            app: 框架应用实例
            config: 监控配置

        Returns:
            中间件实例
        """

    @abstractmethod
    def create_decorator(self, config: "MonitorConfig") -> Callable:
        """
        创建框架特定的装饰器。

        Args:
            config: 监控配置

        Returns:
            装饰器函数
        """

# Flask 适配器示例
@FrameworkRegistry.register("flask")
class FlaskAdapter(BaseAdapter["Flask", "LocalProxy", "Response"]):
    def get_request_path(self, request: "LocalProxy") -> str:
        return request.path

    def get_request_method(self, request: "LocalProxy") -> str:
        return request.method

    def create_middleware(
        self, app: "Flask", config: MonitorConfig
    ) -> "FlaskMiddleware":
        return FlaskMiddleware(app, config)

    def create_decorator(self, config: MonitorConfig) -> Callable:
        return FlaskProfileDecorator(config)
```

---

### BaseMiddleware（中间件基类）

用于实现新框架的中间件。

```python
from abc import ABC, abstractmethod

class BaseMiddleware(ABC):
    """
    中间件抽象基类。

    提供 URL 过滤、告警去重、通知执行的共享实现。
    子类只需实现框架特定的安装和钩子逻辑。
    """

    def __init__(self, config: MonitorConfig):
        self.config = config
        self.url_filter = UrlFilter(config.url_whitelist, config.url_blacklist)
        self.alert_manager = AlertManager(config)
        self.executor = NotificationExecutor(config)

    def should_profile(self, path: str) -> bool:
        """判断指定路径是否需要性能分析（已实现）"""
        return self.url_filter.should_monitor(path)

    def process_profile(self, profile: PerformanceProfile) -> None:
        """处理性能分析结果：检查告警去重并触发通知（已实现）"""
        if self.alert_manager.should_alert(profile.endpoint):
            self.executor.submit(profile)

    @abstractmethod
    def install(self, app: Any) -> None:
        """安装中间件到应用（子类实现）"""

    @abstractmethod
    def _before_request(self) -> None:
        """请求前钩子：启动性能分析（子类实现）"""

    @abstractmethod
    def _after_request(self, response: Any) -> Any:
        """请求后钩子：停止分析并处理结果（子类实现）"""

# Flask 中间件示例
class FlaskMiddleware(BaseMiddleware):
    def install(self, app: Flask) -> None:
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _before_request(self) -> None:
        if self.should_profile(request.path):
            g.profiler = Profiler()
            g.profiler.start()

    def _after_request(self, response: Response) -> Response:
        if hasattr(g, "profiler"):
            g.profiler.stop()
            profile = self._create_profile(g.profiler)
            if profile.duration_seconds > self.config.threshold_seconds:
                self.process_profile(profile)
        return response
```

---

### BaseDecorator（装饰器基类）

用于实现新框架的函数级监控装饰器。

```python
from abc import ABC, abstractmethod
from functools import wraps

class BaseDecorator(ABC):
    """
    装饰器抽象基类。

    提供性能分析和结果处理的共享实现。
    子类只需实现获取框架特定上下文的逻辑。
    """

    def __init__(
        self,
        config: MonitorConfig,
        threshold: Optional[float] = None,
        name: Optional[str] = None
    ):
        self.config = config
        self.threshold = threshold
        self.name = name

    def __call__(self, func: F) -> F:
        """装饰器主入口（已实现）"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            profiler = Profiler()
            profiler.start()
            try:
                return func(*args, **kwargs)
            finally:
                profiler.stop()
                duration = profiler.last_session.duration
                threshold = self.threshold or self.config.threshold_seconds
                if duration > threshold:
                    profile = self._create_profile(
                        func_name=self.name or func.__name__,
                        duration=duration,
                        profiler=profiler,
                        context=self._get_context()
                    )
                    self._process_profile(profile)
        return wrapper

    @abstractmethod
    def _get_context(self) -> Dict[str, Any]:
        """获取框架特定的上下文信息（子类实现）"""

# Flask 装饰器示例
class FlaskProfileDecorator(BaseDecorator):
    def _get_context(self) -> Dict[str, Any]:
        from flask import request, has_request_context
        if has_request_context():
            return {
                "request_path": request.path,
                "request_method": request.method,
                "user_agent": request.user_agent.string,
            }
        return {}
```

---

## 7. 通知器扩展接口

### BaseNotifier（通知器基类）

用于实现自定义通知渠道。

```python
from web_perf_monitor.notifiers import BaseNotifier, register_notifier

class BaseNotifier(ABC):
    @abstractmethod
    def send(
        self,
        profile: PerformanceProfile,
        format: str = "markdown"
    ) -> None:
        """
        发送通知。

        Args:
            profile: 性能分析结果
            format: 消息格式 (markdown/text)

        Raises:
            NotificationError: 发送失败时抛出
        """

    @abstractmethod
    def validate_config(self) -> bool:
        """
        验证配置有效性。

        Returns:
            配置是否有效
        """

# 注册自定义通知器
@register_notifier("slack")
class SlackNotifier(BaseNotifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, profile: PerformanceProfile, format: str = "markdown"):
        # 实现 Slack 通知逻辑
        ...

    def validate_config(self) -> bool:
        return bool(self.webhook_url)
```

---

## 8. 异常类型

```python
from web_perf_monitor.exceptions import (
    WebPerfMonitorError,         # 基础异常
    ConfigurationError,          # 配置错误
    NotificationError,           # 通知发送失败
    ProfilerError,               # 性能分析器错误
)
```

---

## 9. 使用示例

### 最简集成（3 行代码）

```python
from flask import Flask
from web_perf_monitor import PerformanceMiddleware

app = Flask(__name__)
PerformanceMiddleware(app)  # 使用默认配置
```

### 完整配置示例

```python
from flask import Flask
from web_perf_monitor import PerformanceMiddleware, MonitorConfig

app = Flask(__name__)

config = MonitorConfig(
    threshold_seconds=0.5,
    alert_window_days=7,
    log_path="/var/log/myapp",
    url_whitelist=["/api/*"],
    notice_list=[
        {
            "type": "local",
            "format": "markdown"
        },
        {
            "type": "mattermost",
            "format": "markdown",
            "server_url": "https://mm.example.com",
            "token": "xxx",
            "channel_id": "yyy"
        }
    ]
)

PerformanceMiddleware(app, config=config)
```

### 装饰器模式

```python
from web_perf_monitor import profile

@profile()
def process_data(data):
    # 慢操作
    return result

@profile(threshold=0.1, name="critical_db_query")
def query_database():
    # 关键数据库操作
    return results
```

### 环境变量配置

```bash
export PERF_THRESHOLD=0.5
export PERF_ALERT_WINDOW=7
export PERF_LOG_PATH=/var/log/myapp
export PERF_URL_WHITELIST="/api/*,/v1/*"
```

```python
from web_perf_monitor import PerformanceMiddleware, MonitorConfig

app = Flask(__name__)
config = MonitorConfig.from_env()
PerformanceMiddleware(app, config=config)
```

### 扩展新框架（以 Django 为例）

```python
from web_perf_monitor.core import (
    FrameworkRegistry,
    BaseAdapter,
    BaseMiddleware,
    BaseDecorator,
)
from django.http import HttpRequest, HttpResponse

# 1. 实现适配器
@FrameworkRegistry.register("django")
class DjangoAdapter(BaseAdapter["WSGIHandler", HttpRequest, HttpResponse]):
    def get_request_path(self, request: HttpRequest) -> str:
        return request.path

    def get_request_method(self, request: HttpRequest) -> str:
        return request.method

    def create_middleware(self, app, config):
        return DjangoMiddleware(config)

    def create_decorator(self, config):
        return DjangoProfileDecorator(config)

# 2. 实现中间件
class DjangoMiddleware(BaseMiddleware):
    def __init__(self, config):
        super().__init__(config)
        self.get_response = None

    def __call__(self, request):
        if self.should_profile(request.path):
            # 启动分析
            profiler = Profiler()
            profiler.start()
            response = self.get_response(request)
            profiler.stop()
            # 处理结果
            profile = self._create_profile(profiler, request)
            if profile.duration_seconds > self.config.threshold_seconds:
                self.process_profile(profile)
        else:
            response = self.get_response(request)
        return response

# 3. 使用
# settings.py
MIDDLEWARE = [
    'myapp.middleware.DjangoMiddleware',
    # ...
]
```
