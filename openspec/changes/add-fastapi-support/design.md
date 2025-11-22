# Design: FastAPI Framework Support

## Context

FastAPI 是基于 ASGI 的现代异步 Web 框架，与 Flask 的 WSGI 同步模型有本质区别。主要挑战是正确采集异步函数的性能数据，包括：

1. **异步执行模型**: FastAPI 路由处理函数通常是 `async def`，需要在 async context 中进行性能采集
2. **上下文传递**: 请求级状态需要通过 `contextvars` 而非 Flask 的 `g` 对象传递
3. **中间件机制**: Starlette 中间件基于 ASGI 协议，与 Flask 的 before/after_request 不同

## Goals

- 为 FastAPI 应用提供零侵入式性能监控
- 正确采集异步函数的完整调用栈和耗时
- 与 Flask 实现保持一致的配置和 API 风格
- 复用现有的基础组件（告警、过滤、通知）

## Non-Goals

- 支持 WebSocket 连接监控（可作为后续功能）
- 支持 GraphQL 端点监控
- 修改 pyinstrument 核心功能

## Decisions

### Decision 1: 使用 pyinstrument 的 async 支持

pyinstrument 4.0+ 原生支持 async/await 代码的性能分析。通过 `profiler.start()` 和 `profiler.stop()` 可以正确采集异步代码的调用栈。

**选择理由**:
- pyinstrument 已是项目核心依赖，无需引入新依赖
- 4.0+ 版本对 asyncio 有良好支持
- 采样式分析器对异步代码友好，开销低

**替代方案**:
- `yappi`: 更强大的 async 支持，但引入新依赖
- 手动计时: 无法获得调用栈，功能受限

### Decision 2: 使用 Starlette BaseHTTPMiddleware

FastAPI 基于 Starlette，使用 `starlette.middleware.base.BaseHTTPMiddleware` 作为中间件基类。

```python
from starlette.middleware.base import BaseHTTPMiddleware

class FastAPIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # before request
        profiler.start()
        response = await call_next(request)
        profiler.stop()
        # after request
        return response
```

**选择理由**:
- FastAPI 官方推荐方式
- 与 Starlette 生态兼容
- 简单直观

**替代方案**:
- 纯 ASGI 中间件: 更底层，控制更精细，但实现复杂
- FastAPI 依赖注入: 侵入性强，不符合零侵入原则

### Decision 3: 使用 contextvars 存储请求级状态

不同于 Flask 的 `g` 对象，FastAPI/Starlette 使用 `contextvars` 管理请求级上下文。

```python
from contextvars import ContextVar

_profiler_var: ContextVar[Optional[Profiler]] = ContextVar('profiler', default=None)
```

**选择理由**:
- Python 原生支持，无额外依赖
- 对 asyncio 友好，自动处理协程上下文传播
- Starlette 内部也使用此方式

### Decision 4: 同时支持同步和异步路由处理函数

FastAPI 支持同步和异步两种路由处理函数：

```python
@app.get("/sync")
def sync_endpoint():
    return {"status": "ok"}

@app.get("/async")
async def async_endpoint():
    await asyncio.sleep(0.1)
    return {"status": "ok"}
```

中间件需要统一处理这两种情况，pyinstrument 可以正确处理两者。

### Decision 5: 复用现有 Profiler 类

现有的 `Profiler` 类封装了 pyinstrument，对异步代码的支持已经内置。无需创建单独的 `AsyncProfiler` 类。

验证点：
- pyinstrument 在 async context 中调用 `start()/stop()` 可以正确采集异步调用栈
- `get_html_report()` 和 `get_text_report()` 对异步代码同样有效

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI App                          │
├─────────────────────────────────────────────────────────┤
│                  FastAPIMiddleware                       │
│  ┌─────────────────────────────────────────────────┐    │
│  │  1. URL Filter check                             │    │
│  │  2. Start Profiler (contextvars)                 │    │
│  │  3. await call_next(request)                     │    │
│  │  4. Stop Profiler                                │    │
│  │  5. Check threshold                              │    │
│  │  6. Process profile (alert, notify)              │    │
│  └─────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────┤
│              Shared Components (from BaseMiddleware)     │
│  ┌────────────┐ ┌──────────────┐ ┌─────────────────┐    │
│  │ UrlFilter  │ │ AlertManager │ │ NotificationExec│    │
│  └────────────┘ └──────────────┘ └─────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
src/web_perfmonitor/frameworks/fastapi/
├── __init__.py          # 导出 FastAPIMiddleware, FastAPIAdapter
├── adapter.py           # FastAPIAdapter 实现
├── middleware.py        # FastAPIMiddleware 实现
└── decorator.py         # FastAPIProfileDecorator 实现
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| BaseHTTPMiddleware 对流式响应支持有限 | 文档说明，复杂场景建议使用纯 ASGI |
| 长时间运行的 async 操作可能导致内存问题 | 设置合理的超时，文档警告 |
| contextvars 在某些边缘情况可能丢失 | 添加防御性检查，记录警告日志 |

## Migration Plan

这是新增功能，无需迁移。

## Open Questions

1. ~~是否需要支持 FastAPI 的依赖注入获取 profile 结果？~~ - 不需要，保持零侵入
2. ~~是否支持 WebSocket？~~ - 不在此次范围，可后续扩展
