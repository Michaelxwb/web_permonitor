# Sanic Performance Monitor Specification

## ADDED Requirements

### Requirement: Sanic Middleware Integration

系统 SHALL 提供 Sanic 中间件 (`SanicMiddleware`),用于自动监控所有 HTTP 请求的性能。

中间件 SHALL 使用 Sanic 的 request/response 中间件机制实现。

中间件 SHALL 使用 `request.ctx` 对象存储请求级状态,确保在异步上下文中正确传递 profiler 实例。

#### Scenario: Basic Sanic integration

- **GIVEN** 一个 Sanic 应用
- **WHEN** 用户使用 `PerformanceMiddleware(app)` 初始化
- **THEN** 系统自动检测 Sanic 框架并安装 `SanicMiddleware`
- **AND** 所有后续 HTTP 请求都会被自动监控

#### Scenario: Async route profiling

- **GIVEN** Sanic 应用已安装性能监控中间件
- **AND** 配置阈值为 0.5 秒
- **WHEN** 用户请求一个异步路由 `async def slow_endpoint()` 耗时 1.0 秒
- **THEN** 系统正确采集完整的异步调用栈
- **AND** 生成包含 `await` 调用信息的性能报告
- **AND** 触发告警通知

#### Scenario: Sync route profiling

- **GIVEN** Sanic 应用已安装性能监控中间件
- **AND** 配置阈值为 0.5 秒
- **WHEN** 用户请求一个同步路由 `def sync_endpoint()` 耗时 1.0 秒
- **THEN** 系统正确采集同步调用栈
- **AND** 生成性能报告
- **AND** 触发告警通知

### Requirement: Sanic Adapter Registration

系统 SHALL 提供 `SanicAdapter` 类,实现 `BaseAdapter` 接口,并自动注册到 `FrameworkRegistry`。

适配器 SHALL 支持自动检测 Sanic 应用实例。

#### Scenario: Auto-detection of Sanic app

- **GIVEN** 用户有一个 Sanic 应用实例
- **WHEN** 调用 `PerformanceMiddleware(app)`
- **THEN** `FrameworkRegistry.auto_detect()` 返回 `SanicAdapter`
- **AND** 系统使用 Sanic 特定的中间件和装饰器

#### Scenario: Manual framework specification

- **GIVEN** 用户有一个 Sanic 应用实例
- **WHEN** 调用 `PerformanceMiddleware(app, framework="sanic")`
- **THEN** 系统使用 `SanicAdapter` 而不进行自动检测

### Requirement: Sanic Profile Decorator

系统 SHALL 提供 `SanicProfileDecorator`,支持对单个异步函数进行性能监控。

装饰器 SHALL 同时支持 `async def` 和普通 `def` 函数。

#### Scenario: Async function profiling with decorator

- **GIVEN** 用户使用 `@profile()` 装饰一个异步函数
- **WHEN** 调用该函数
- **THEN** 系统正确测量异步执行时间
- **AND** 生成包含异步调用栈的性能报告

#### Scenario: Custom threshold for decorator

- **GIVEN** 用户使用 `@profile(threshold=0.1)` 装饰函数
- **WHEN** 函数执行耗时 0.15 秒
- **THEN** 触发性能报告生成
- **AND** 使用自定义阈值而非全局配置

### Requirement: Request Metadata Collection

`SanicMiddleware` SHALL 收集请求元数据,与 Flask/FastAPI 中间件保持一致的数据结构。

收集的元数据 SHALL 包括: URL、路径、HTTP 方法、客户端 IP、User-Agent、查询参数、请求体(JSON)。

#### Scenario: Metadata included in profile

- **GIVEN** Sanic 应用已安装性能监控
- **WHEN** 请求 `POST /api/users?page=1` 带 JSON body `{"name": "test"}`
- **THEN** 生成的 `PerformanceProfile` 包含:
  - `url`: 完整请求 URL
  - `path`: `/api/users`
  - `method`: `POST`
  - `query_params`: `{"page": "1"}`
  - `json_body`: `{"name": "test"}`

### Requirement: Consistent Configuration

Sanic 支持 SHALL 复用现有的 `MonitorConfig` 配置系统。

所有配置项(阈值、告警窗口、URL 过滤、通知列表等) SHALL 与 Flask/FastAPI 行为一致。

#### Scenario: URL filtering

- **GIVEN** 配置 `url_blacklist=["/health", "/metrics"]`
- **WHEN** 请求 `/health` 端点
- **THEN** 该请求不被性能监控

#### Scenario: Alert deduplication

- **GIVEN** 配置 `alert_window_days=10`
- **AND** 端点 `/api/slow` 在过去 10 天内已触发告警
- **WHEN** 同一端点再次超过阈值
- **THEN** 不发送重复告警

### Requirement: Zero Intrusion

Sanic 中间件 SHALL 遵循零侵入原则:

- 监控功能不得修改请求或响应内容
- 监控错误不得影响应用正常运行
- 不得要求用户修改路由处理函数

#### Scenario: Profiler error isolation

- **GIVEN** Sanic 应用已安装性能监控
- **WHEN** profiler 内部发生异常
- **THEN** 请求正常处理并返回
- **AND** 错误被记录到日志
- **AND** 用户无感知

#### Scenario: Response passthrough

- **GIVEN** Sanic 应用已安装性能监控
- **WHEN** 路由返回任意响应(JSON、流式、文件等)
- **THEN** 响应内容和 headers 不被修改

### Requirement: Optional Dependency

Sanic 支持 SHALL 作为可选依赖,不影响核心包的安装和使用。

#### Scenario: Installation without Sanic

- **GIVEN** 用户只需要 Flask 或 FastAPI 支持
- **WHEN** 安装 `pip install web-perfmonitor`
- **THEN** 不安装 Sanic 相关依赖
- **AND** Flask/FastAPI 功能正常可用

#### Scenario: Installation with Sanic

- **GIVEN** 用户需要 Sanic 支持
- **WHEN** 安装 `pip install web-perfmonitor[sanic]`
- **THEN** 安装 Sanic 依赖
- **AND** Sanic 功能正常可用

### Requirement: Request Context Integration

`SanicMiddleware` SHALL 使用 Sanic 的 `request.ctx` 对象存储 profiler 实例。

中间件 SHALL 在请求开始时创建 profiler 并存储在 `request.ctx._perf_monitor_profiler`。

中间件 SHALL 在响应生成后停止 profiler 并清理 ctx 对象。

#### Scenario: Profiler lifecycle management

- **GIVEN** Sanic 应用已安装性能监控中间件
- **WHEN** 处理一个请求
- **THEN** 在请求处理前 `request.ctx._perf_monitor_profiler` 被创建
- **AND** 在响应生成后该属性被清理
- **AND** 不同请求的 profiler 实例互不干扰

#### Scenario: Exception handling cleanup

- **GIVEN** Sanic 应用已安装性能监控中间件
- **WHEN** 请求处理过程中发生异常
- **THEN** profiler 仍然被正确停止
- **AND** `request.ctx` 中的 profiler 引用被清理
- **AND** 不造成内存泄漏
