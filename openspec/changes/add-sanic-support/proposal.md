# Change: Add Sanic Framework Support

## Why

当前项目支持 Flask (同步/WSGI) 和 FastAPI (异步/ASGI) 框架。Sanic 是另一个流行的 Python 异步 Web 框架,专为高性能设计,在国内外都有广泛应用。为了扩大项目的适用范围,需要添加对 Sanic 的支持。

Sanic 基于 uvloop 和 httptools,原生支持 async/await,并提供了独特的中间件系统。虽然同为异步框架,但 Sanic 的中间件机制与 FastAPI/Starlette 不同,需要专门的适配实现。

## What Changes

- **ADDED** Sanic 框架适配器 (`SanicAdapter`),实现 `BaseAdapter` 接口
- **ADDED** Sanic 中间件 (`SanicMiddleware`),基于 Sanic 中间件机制
- **ADDED** Sanic 函数装饰器 (`SanicProfileDecorator`),支持异步函数分析
- **ADDED** Sanic 作为可选依赖到 `pyproject.toml`
- **复用** 现有的异步分析器、告警去重、URL 过滤、通知系统等基础组件

## Impact

- **Affected specs**: 新增 `sanic-perf-monitor` 能力规范
- **Affected code**:
  - `src/web_perfmonitor/frameworks/sanic/` - 新目录,包含适配器、中间件、装饰器
  - `pyproject.toml` - 添加 sanic 可选依赖
  - `src/web_perfmonitor/__init__.py` - 导出 Sanic 相关 API
- **Dependencies**:
  - `sanic >= 21.0.0` (作为可选依赖)

## Compatibility

- 与现有 Flask 和 FastAPI 实现完全兼容,不影响现有功能
- 遵循相同的配置机制 (`MonitorConfig`)
- 复用现有的告警去重、URL 过滤、通知系统等基础组件
- API 风格与 Flask/FastAPI 保持一致,降低学习成本

## Risk Assessment

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| Sanic 中间件机制不同 | 中 | 中 | 参考官方文档,使用 request/response 中间件 |
| 异步上下文传递复杂 | 低 | 中 | 使用 Sanic 的 ctx 对象存储请求级状态 |
| 性能开销过高 | 低 | 中 | 基准测试,确保开销 < 5% |
