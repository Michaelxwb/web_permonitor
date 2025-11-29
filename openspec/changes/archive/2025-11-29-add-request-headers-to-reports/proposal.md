# Change: Add Request Headers to MD Reports

## Why

当前的性能监控报告（Markdown 格式）只包含基本的请求信息（URL、方法、查询参数、请求体等），但缺少关键的 HTTP 请求头信息。在实际的生产环境中，以下请求头对性能问题排查至关重要：

- **X-Forwarded-For / X-Real-IP**: 真实客户端 IP（在负载均衡/反向代理场景）
- **X-Request-ID / X-Trace-ID / X-Correlation-ID**: 分布式追踪标识，用于关联日志和调用链
- **Referer**: 请求来源，帮助理解用户访问路径
- **Content-Type**: 请求数据格式
- **Accept**: 客户端期望的响应格式
- **Accept-Language**: 客户端语言偏好
- **Origin**: CORS 请求来源

这些信息可以帮助：
1. 定位特定客户端或地区的性能问题
2. 关联分布式追踪系统的调用链
3. 分析跨域请求的性能特征
4. 理解不同请求格式的性能差异

## What Changes

- **MODIFIED** `BaseNotifier._format_markdown()` 方法，在"请求详情"部分添加"请求头"展示
- **MODIFIED** Flask 中间件的 `_get_request_metadata()` 方法，收集常用的非敏感 HTTP 请求头
- **MODIFIED** FastAPI 中间件的 `_get_request_metadata()` 方法，收集常用的非敏感 HTTP 请求头
- **ADDED** 配置选项 `capture_request_headers`（默认 True）控制是否收集请求头
- **ADDED** 配置选项 `included_headers`（默认包含追踪、来源等常用头）允许用户自定义需要收集的请求头列表

默认收集的请求头：
- `X-Forwarded-For`
- `X-Real-IP`
- `X-Request-ID`
- `X-Trace-ID`
- `X-Correlation-ID`
- `Referer`
- `Content-Type`
- `Accept`
- `Accept-Language`
- `Origin`
- `User-Agent`（已有，保持兼容）

## Impact

- **Affected specs**: 创建或修改通用监控能力规范
- **Affected code**:
  - `src/web_perfmonitor/notifiers/base.py` - 修改 `_format_markdown()` 方法添加请求头展示
  - `src/web_perfmonitor/frameworks/flask/middleware.py` - 修改 `_get_request_metadata()` 方法收集请求头
  - `src/web_perfmonitor/frameworks/fastapi/middleware.py` - 修改 `_get_request_metadata()` 方法收集请求头
  - `src/web_perfmonitor/config.py` - 添加 `capture_request_headers` 和 `included_headers` 配置
  - `src/web_perfmonitor/models.py` - 文档更新（metadata 字段说明）
- **Dependencies**: 无新增依赖

## Compatibility

- **向后兼容**: 新字段 `request_headers` 在 metadata 中可选，不影响现有报告
- **配置兼容**: 新配置项有合理默认值，无需用户修改配置即可使用
- **安全性**: 只收集非敏感的追踪和来源相关请求头，不包含认证信息

## Risk Assessment

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 报告文件轻微增大 | 低 | 低 | 请求头数量有限且值较短，影响可忽略 |
| 性能开销增加 | 低 | 低 | 请求头读取是轻量操作，开销可忽略 |
| 部分头不存在导致空值 | 高 | 无 | 只展示存在的请求头，空值不影响功能 |
