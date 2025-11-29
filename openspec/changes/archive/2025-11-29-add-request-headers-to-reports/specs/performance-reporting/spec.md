# Capability: Performance Reporting

性能监控报告生成能力，支持多种格式（HTML、Markdown、Text）的性能分析报告。

## ADDED Requirements

### Requirement: Request Header Collection

系统 SHALL 收集并展示 HTTP 请求头信息，以支持性能问题的深度分析和分布式追踪。

#### Scenario: 收集追踪相关请求头

**Given** 一个 HTTP 请求包含分布式追踪标识（如 X-Request-ID）
**When** 请求响应时间超过阈值触发性能分析
**Then** 系统应在 metadata 中记录该请求头及其值

#### Scenario: 收集客户端来源信息

**Given** 一个 HTTP 请求通过反向代理转发，包含 X-Forwarded-For 头
**When** 请求响应时间超过阈值触发性能分析
**Then** 系统应在 metadata 中记录真实客户端 IP 地址

#### Scenario: 支持可配置的请求头列表

**Given** 用户配置了自定义的 `included_headers` 列表
**When** 系统收集请求元数据
**Then** 应只收集配置列表中指定的请求头

#### Scenario: 默认请求头列表

**Given** 用户未配置自定义请求头列表
**When** 系统收集请求元数据
**Then** 应收集以下默认请求头（如果存在）：
- X-Forwarded-For
- X-Real-IP
- X-Request-ID
- X-Trace-ID
- X-Correlation-ID
- Referer
- Content-Type
- Accept
- Accept-Language
- Origin
- User-Agent

### Requirement: Markdown Report Header Display

系统 SHALL 在 Markdown 格式报告中展示收集到的请求头信息。

#### Scenario: 在 Markdown 报告中展示请求头

**Given** 一个性能分析报告包含请求头信息
**When** 生成 Markdown 格式报告
**Then** 报告应包含"请求头"章节，以列表形式展示所有收集到的请求头

#### Scenario: 请求头不存在时的处理

**Given** 一个性能分析报告不包含任何请求头信息
**When** 生成 Markdown 格式报告
**Then** 报告不应显示空的"请求头"章节

#### Scenario: 请求头值过长时的处理

**Given** 一个请求头的值长度超过 500 字符
**When** 记录该请求头到 metadata
**Then** 系统应截断该值并添加省略标记（...）

### Requirement: Configuration Support

系统 SHALL 提供配置选项控制请求头收集行为。

#### Scenario: 禁用请求头收集

**Given** 用户设置 `capture_request_headers = False`
**When** 系统收集请求元数据
**Then** 不应收集任何请求头信息（User-Agent 除外，保持向后兼容）

#### Scenario: 启用请求头收集（默认行为）

**Given** 用户未配置 `capture_request_headers` 或设置为 True
**When** 系统收集请求元数据
**Then** 应按默认列表收集请求头信息

#### Scenario: 自定义请求头列表

**Given** 用户配置 `included_headers = ["X-Custom-ID", "X-Session-ID"]`
**When** 系统收集请求元数据
**Then** 应只收集指定的两个请求头（加上 User-Agent 保持兼容）
