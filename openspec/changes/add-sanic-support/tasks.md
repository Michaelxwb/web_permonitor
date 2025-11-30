# Tasks: Add Sanic Framework Support

## 1. Project Setup

- [x] 1.1 更新 `pyproject.toml` 添加 Sanic 可选依赖
  - 添加 `sanic >= 21.0.0` 到 optional dependencies
  - 创建 `[sanic]` extra group
- [x] 1.2 创建 `src/web_perfmonitor/frameworks/sanic/` 目录结构
  - 创建 `__init__.py`
  - 创建 `adapter.py`
  - 创建 `middleware.py`
  - 创建 `decorator.py`

## 2. Core Implementation

- [x] 2.1 实现 `SanicAdapter` (`adapter.py`)
  - 继承 `BaseAdapter`
  - 使用 `@FrameworkRegistry.register("sanic")` 注册
  - 实现 `can_handle()` 检测 Sanic 应用
  - 实现 `get_request_path()` 和 `get_request_method()`
  - 实现 `create_middleware()` 和 `create_decorator()`

- [x] 2.2 实现 `SanicMiddleware` (`middleware.py`)
  - 继承 `BaseMiddleware`
  - 使用 Sanic 的 request/response 中间件机制
  - 使用 `request.ctx` 存储 profiler 实例
  - 实现请求前启动 profiler
  - 实现响应后停止 profiler 并处理结果
  - 实现 `_build_endpoint_key()` 构建端点标识
  - 实现 `_get_request_metadata()` 收集请求元数据
  - 添加异常隔离确保零侵入

- [x] 2.3 实现 `SanicProfileDecorator` (`decorator.py`)
  - 继承 `BaseDecorator`
  - 支持 `async def` 函数 (使用 `inspect.iscoroutinefunction`)
  - 支持普通 `def` 函数
  - 实现 `_get_context()` 获取 Sanic 请求上下文

## 3. Integration

- [x] 3.1 更新 `src/web_perfmonitor/frameworks/__init__.py`
  - 条件导入 Sanic 模块(避免硬依赖)

- [x] 3.2 更新 `src/web_perfmonitor/__init__.py`
  - 添加 Sanic 相关导出(条件性)
  - 更新 `__all__` 列表

## 4. Testing

- [ ] 4.1 创建 Sanic 单元测试 (`tests/unit/frameworks/test_sanic_*.py`)
  - `test_sanic_adapter.py`: 测试适配器功能
  - `test_sanic_middleware.py`: 测试中间件功能
  - `test_sanic_decorator.py`: 测试装饰器功能

- [ ] 4.2 创建 Sanic 集成测试 (`tests/integration/test_sanic_integration.py`)
  - 测试完整的请求-响应流程
  - 测试异步路由性能采集
  - 测试同步路由性能采集
  - 测试 URL 过滤
  - 测试告警去重
  - 测试通知发送

- [ ] 4.3 验证异步采集正确性
  - 测试 `asyncio.sleep()` 是否正确计入耗时
  - 测试 `await` 调用是否出现在调用栈
  - 测试并发请求是否互不干扰

## 5. Documentation & Examples

- [x] 5.1 创建 Sanic 示例应用 (`examples/sanic_demo.py`)
  - 快速端点示例
  - 慢速异步端点示例
  - 慢速同步端点示例
  - API 端点示例
  - 健康检查端点(排除监控)

- [x] 5.2 更新 README.md
  - 添加 Sanic 快速开始示例
  - 添加安装说明 `pip install web-perfmonitor[sanic]`

- [x] 5.3 更新 README_CN.md
  - 添加 Sanic 中文文档

## 6. Validation

- [ ] 6.1 运行完整测试套件
  - `pytest tests/`
  - 确保所有测试通过

- [ ] 6.2 手动测试示例应用
  - 运行 `python examples/sanic_demo.py`
  - 验证性能报告生成正确

## Dependencies

```
1.1 → 1.2 → 2.1 → 2.2 → 2.3 (顺序依赖)
2.1, 2.2, 2.3 → 3.1, 3.2 (需要核心实现完成)
2.1, 2.2, 2.3 → 4.1, 4.2, 4.3 (需要核心实现完成)
4.1, 4.2, 4.3 → 6.1 (测试完成后验证)
5.1 → 6.2 (示例完成后验证)
```

## Parallelizable Work

- 4.1, 4.2, 4.3 可并行进行(测试之间无依赖)
- 5.1, 5.2, 5.3 可并行进行(文档之间无依赖)
