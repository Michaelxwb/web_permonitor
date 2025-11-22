# Change: Add FastAPI Framework Support

## Why

当前项目只支持 Flask 框架的性能监控。FastAPI 是现代 Python Web 开发中最流行的异步框架之一，广泛用于构建高性能 API。为了满足更多用户的需求，需要添加对 FastAPI 的支持。

FastAPI 基于 Starlette 和 Pydantic，使用 ASGI 协议，支持原生 async/await。这与 Flask 的 WSGI 同步模型有本质区别，因此需要专门处理异步函数的性能采集。

## What Changes

- **ADDED** FastAPI 框架适配器 (`FastAPIAdapter`)，实现 `BaseAdapter` 接口
- **ADDED** FastAPI 中间件 (`FastAPIMiddleware`)，基于 Starlette 中间件机制
- **ADDED** FastAPI 函数装饰器 (`FastAPIProfileDecorator`)，支持异步函数分析
- **ADDED** 异步分析器支持 (`AsyncProfiler`)，正确采集异步函数的调用栈和耗时
- **ADDED** FastAPI 作为可选依赖到 `pyproject.toml`

## Impact

- **Affected specs**: 新增 `fastapi-perf-monitor` 能力规范
- **Affected code**:
  - `src/web_perfmonitor/frameworks/fastapi/` - 新目录，包含适配器、中间件、装饰器
  - `src/web_perfmonitor/profiler.py` - 可能需要扩展以支持异步
  - `pyproject.toml` - 添加 fastapi 可选依赖
  - `src/web_perfmonitor/__init__.py` - 导出 FastAPI 相关 API
- **Dependencies**:
  - `fastapi >= 0.100.0`
  - `starlette >= 0.27.0` (FastAPI 的底层框架)

## Compatibility

- 与现有 Flask 实现完全兼容，不影响现有功能
- 遵循相同的配置机制 (`MonitorConfig`)
- 复用现有的告警去重、URL 过滤、通知系统等基础组件
- API 风格与 Flask 保持一致，降低学习成本

## Risk Assessment

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| pyinstrument 对 async 支持不完整 | 中 | 高 | 测试验证，必要时使用 async 友好的采样方式 |
| 异步上下文传递复杂 | 中 | 中 | 使用 contextvars 管理请求级状态 |
| 性能开销过高 | 低 | 中 | 基准测试，确保开销 < 5% |
