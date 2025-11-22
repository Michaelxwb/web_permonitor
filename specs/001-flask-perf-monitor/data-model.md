# 数据模型：Web 性能监控告警系统

**日期**: 2025-11-22
**关联计划**: [plan.md](./plan.md)

## 实体关系图

```
                        ┌─────────────────┐
                        │ FrameworkRegistry│  (框架注册器)
                        └─────────────────┘
                               │
                               │ 注册
                               ▼
┌─────────────────┐     ┌─────────────────┐
│  BaseAdapter    │◀────│  FlaskAdapter   │  (框架适配器)
│   (抽象基类)     │     │ DjangoAdapter   │
└─────────────────┘     └─────────────────┘
        │                      │
        │ 使用                  │ 创建
        ▼                      ▼
┌─────────────────┐     ┌─────────────────┐
│  BaseMiddleware │◀────│ FlaskMiddleware │  (中间件)
│   (抽象基类)     │     │DjangoMiddleware │
└─────────────────┘     └─────────────────┘
        │
        │ 依赖
        ▼
┌─────────────────┐     ┌─────────────────┐
│ MonitorConfig   │────▶│   UrlFilter     │
└─────────────────┘     └─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐
│NotificationConfig│
└─────────────────┘
        │
        │ 创建
        ▼
┌─────────────────┐     ┌─────────────────┐
│NotificationTask │◀────│PerformanceProfile│
└─────────────────┘     └─────────────────┘
                               │
                               │ 触发
                               ▼
                        ┌─────────────────┐
                        │  AlertRecord    │
                        └─────────────────┘
```

---

## 框架抽象实体

### FrameworkRegistry（框架注册器）

全局单例，管理所有已注册的框架适配器。

| 字段 | 类型 | 描述 |
|------|------|------|
| _adapters | Dict[str, Type[BaseAdapter]] | 已注册的适配器类映射 |

**方法**:
| 方法 | 签名 | 描述 |
|------|------|------|
| register | `(name: str) -> Callable` | 装饰器，注册框架适配器 |
| get | `(name: str) -> Type[BaseAdapter]` | 获取指定框架的适配器类 |
| list_frameworks | `() -> List[str]` | 列出所有已注册的框架名称 |
| auto_detect | `(app: Any) -> Optional[BaseAdapter]` | 自动检测应用类型并返回适配器 |

**使用示例**:
```python
@FrameworkRegistry.register("flask")
class FlaskAdapter(BaseAdapter):
    ...

# 获取适配器
adapter_cls = FrameworkRegistry.get("flask")
adapter = adapter_cls()

# 自动检测
adapter = FrameworkRegistry.auto_detect(flask_app)
```

---

### BaseAdapter（框架适配器抽象基类）

定义框架适配器的标准接口，使用泛型支持类型安全。

| 泛型参数 | 描述 |
|----------|------|
| AppType | 框架应用类型（如 Flask, Django） |
| RequestType | 请求对象类型 |
| ResponseType | 响应对象类型 |

**抽象方法**:
| 方法 | 签名 | 描述 |
|------|------|------|
| get_request_path | `(request: RequestType) -> str` | 从请求中提取路径 |
| get_request_method | `(request: RequestType) -> str` | 从请求中提取 HTTP 方法 |
| create_middleware | `(app: AppType, config: MonitorConfig) -> BaseMiddleware` | 创建框架特定的中间件 |
| create_decorator | `(config: MonitorConfig) -> Callable` | 创建框架特定的装饰器 |

**Flask 实现**: `FlaskAdapter[Flask, LocalProxy, Response]`
**Django 实现（未来）**: `DjangoAdapter[WSGIHandler, HttpRequest, HttpResponse]`

---

### BaseMiddleware（中间件抽象基类）

定义中间件的标准接口和共享逻辑。

| 字段 | 类型 | 描述 |
|------|------|------|
| config | MonitorConfig | 监控配置 |
| url_filter | UrlFilter | URL 过滤器 |
| alert_manager | AlertManager | 告警管理器 |
| executor | NotificationExecutor | 通知执行器 |

**具体方法（已实现）**:
| 方法 | 签名 | 描述 |
|------|------|------|
| should_profile | `(path: str) -> bool` | 判断是否需要分析（URL 过滤） |
| process_profile | `(profile: PerformanceProfile) -> None` | 处理分析结果（去重+通知） |

**抽象方法（需实现）**:
| 方法 | 签名 | 描述 |
|------|------|------|
| install | `(app: Any) -> None` | 安装中间件到应用 |
| _before_request | `() -> None` | 请求前钩子 |
| _after_request | `(response: Any) -> Any` | 请求后钩子 |

---

### BaseDecorator（装饰器抽象基类）

定义函数级监控装饰器的标准接口。

| 字段 | 类型 | 描述 |
|------|------|------|
| config | MonitorConfig | 监控配置 |
| threshold | Optional[float] | 自定义阈值（覆盖全局配置） |
| name | Optional[str] | 自定义名称 |

**具体方法（已实现）**:
| 方法 | 签名 | 描述 |
|------|------|------|
| __call__ | `(func: F) -> F` | 装饰器主入口 |
| _create_profile | `(func_name: str, duration: float, ...) -> PerformanceProfile` | 创建分析结果 |

**抽象方法（需实现）**:
| 方法 | 签名 | 描述 |
|------|------|------|
| _get_context | `() -> Dict[str, Any]` | 获取框架特定的上下文信息 |

---

## 核心实体

### 1. MonitorConfig（监控配置）

全局监控配置，控制系统行为。

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| threshold_seconds | float | 1.0 | 性能阈值（秒），超过则触发告警 |
| alert_window_days | int | 10 | 告警去重窗口（天） |
| max_performance_overhead | float | 0.05 | 最大允许性能开销比例 |
| log_path | str | "/tmp" | 日志和报告输出目录 |
| url_whitelist | List[str] | [] | URL 白名单 |
| url_blacklist | List[str] | [] | URL 黑名单 |
| notice_list | List[NotificationConfig] | [] | 通知渠道配置列表 |
| notice_timeout_seconds | float | 30.0 | 单个通知渠道超时时间 |
| notice_queue_size | int | 1000 | 通知任务队列最大长度 |
| graceful_shutdown_seconds | float | 5.0 | 优雅关闭等待时间 |

**验证规则**:
- threshold_seconds > 0
- alert_window_days >= 0
- 0 < max_performance_overhead <= 1
- notice_timeout_seconds > 0
- notice_queue_size > 0

---

### 2. UrlFilter（URL 过滤器）

控制哪些 URL 需要被监控。

| 字段 | 类型 | 描述 |
|------|------|------|
| whitelist | List[str] | URL 白名单模式列表 |
| blacklist | List[str] | URL 黑名单模式列表 |

**业务规则**:
- 白名单非空时，黑名单被忽略
- 支持精确匹配：`/api/users`
- 支持通配符匹配：`/api/*`、`*/health`
- 空白名单 + 空黑名单 = 监控所有 URL

**状态转换**: 无（配置对象）

---

### 3. NotificationConfig（通知渠道配置）

单个通知渠道的配置，采用扁平结构。

**通用字段**:
| 字段 | 类型 | 描述 |
|------|------|------|
| type | str | 通知类型（local/mattermost） |
| format | str | 消息格式（markdown/text） |

**Local 类型附加字段**:
| 字段 | 类型 | 描述 |
|------|------|------|
| output_dir | str | 报告输出目录（可选，默认使用 log_path） |

**Mattermost 类型附加字段**:
| 字段 | 类型 | 描述 |
|------|------|------|
| server_url | str | Mattermost 服务器地址 |
| token | str | API Token |
| channel_id | str | 目标频道 ID |

**配置示例**:
```python
# Local 通知
{"type": "local", "format": "markdown"}

# Mattermost 通知
{
    "type": "mattermost",
    "format": "markdown",
    "server_url": "https://mattermost.example.com",
    "token": "your-api-token",
    "channel_id": "channel-id"
}
```

**验证规则**:
- type 必须是已注册的通知器类型
- format 必须是 "markdown" 或 "text"
- 各类型的必需字段必须存在

---

### 4. PerformanceProfile（性能分析结果）

一次性能采集的完整结果。

| 字段 | 类型 | 描述 |
|------|------|------|
| id | str | 唯一标识（UUID） |
| endpoint | str | 接口路径或函数名 |
| method | str | HTTP 方法（中间件模式）或 "FUNCTION"（装饰器模式） |
| duration_seconds | float | 执行时间（秒） |
| timestamp | datetime | 采集时间 |
| html_report | str | pyinstrument HTML 格式报告 |
| text_report | str | pyinstrument 文本格式报告 |
| metadata | Dict[str, Any] | 扩展元数据 |

**metadata 示例**:
```json
{
  "request_id": "abc-123",
  "user_agent": "Mozilla/5.0...",
  "query_params": {"page": "1"},
  "status_code": 200
}
```

**验证规则**:
- id 必须唯一
- duration_seconds >= 0
- endpoint 不能为空

---

### 5. AlertRecord（告警记录）

用于告警去重的记录。

| 字段 | 类型 | 描述 |
|------|------|------|
| endpoint | str | 接口路径或函数名（主键） |
| last_alert_time | datetime | 最后一次告警时间 |
| alert_count | int | 累计告警次数 |

**业务规则**:
- 同一 endpoint 在 alert_window_days 内只告警一次
- 超过窗口期后重新计算

**状态转换**:
```
新接口 ──触发告警──▶ 已告警 ──窗口期内再次触发──▶ 已告警（计数+1，不发送）
                        │
                        │ 超过窗口期
                        ▼
                    可再次告警
```

---

### 6. NotificationTask（通知任务）

一个待执行的异步通知任务。

| 字段 | 类型 | 描述 |
|------|------|------|
| id | str | 任务唯一标识 |
| profile | PerformanceProfile | 关联的性能分析结果 |
| notifiers | List[NotificationConfig] | 目标通知渠道列表 |
| created_at | datetime | 任务创建时间 |
| status | TaskStatus | 任务状态 |
| errors | List[str] | 执行错误列表 |

**TaskStatus 枚举**:
| 值 | 描述 |
|------|------|
| PENDING | 等待执行 |
| RUNNING | 正在执行 |
| COMPLETED | 执行完成（可能部分失败） |
| FAILED | 全部失败 |
| TIMEOUT | 超时放弃 |

**状态转换**:
```
PENDING ──开始执行──▶ RUNNING ──全部成功──▶ COMPLETED
                         │
                         ├──部分成功──▶ COMPLETED（带 errors）
                         │
                         ├──全部失败──▶ FAILED
                         │
                         └──超时──▶ TIMEOUT
```

---

## 持久化策略

| 实体 | 存储方式 | 位置 |
|------|----------|------|
| MonitorConfig | 内存（启动时加载） | 代码/环境变量 |
| UrlFilter | 内存（MonitorConfig 的一部分） | - |
| NotificationConfig | 内存（MonitorConfig 的一部分） | - |
| PerformanceProfile | 本地文件（可选） | `{log_path}/reports/` |
| AlertRecord | JSON 文件 + 内存缓存 | `{log_path}/alerts.json` |
| NotificationTask | 内存队列（不持久化） | - |

---

## 文件存储格式

### alerts.json

```json
{
  "records": {
    "/api/users": {
      "endpoint": "/api/users",
      "last_alert_time": "2025-11-22T10:30:00Z",
      "alert_count": 3
    },
    "/api/orders": {
      "endpoint": "/api/orders",
      "last_alert_time": "2025-11-20T15:45:00Z",
      "alert_count": 1
    }
  },
  "metadata": {
    "version": "1.0",
    "last_updated": "2025-11-22T10:30:00Z"
  }
}
```

### 性能报告文件命名

```
{log_path}/reports/{endpoint_safe}_{timestamp}_{id}.html
{log_path}/reports/{endpoint_safe}_{timestamp}_{id}.txt
```

示例：
```
/tmp/reports/api_users_20251122_103000_abc123.html
/tmp/reports/api_users_20251122_103000_abc123.txt
```
