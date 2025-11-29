# Implementation Tasks

## Task 1: 添加配置选项 ✅

在 `config.py` 中添加请求头收集相关的配置项。

**Validation:**
- `MonitorConfig` 类包含 `capture_request_headers: bool` 字段（默认 True）
- `MonitorConfig` 类包含 `included_headers: Optional[List[str]]` 字段（默认 None）
- 配置项支持通过环境变量设置（`PERF_CAPTURE_REQUEST_HEADERS`, `PERF_INCLUDED_HEADERS`）
- 类型检查通过（mypy）

**Dependencies:** 无

## Task 2: 修改 Flask 中间件收集请求头 ✅

修改 `frameworks/flask/middleware.py` 的 `_get_request_metadata()` 方法收集请求头。

**Validation:**
- 当 `capture_request_headers=True` 时，metadata 包含 `request_headers` 字典
- 默认收集 11 个标准请求头（X-Forwarded-For, X-Real-IP, X-Request-ID, X-Trace-ID, X-Correlation-ID, Referer, Content-Type, Accept, Accept-Language, Origin, User-Agent）
- 当请求头不存在时，不添加到 `request_headers` 字典
- 请求头值长度超过 500 字符时进行截断
- 当配置了 `included_headers` 时，只收集指定的请求头
- 当 `capture_request_headers=False` 时，不收集请求头（User-Agent 保持兼容）

**Dependencies:** Task 1

## Task 3: 修改 FastAPI 中间件收集请求头 ✅

修改 `frameworks/fastapi/middleware.py` 的 `_get_request_metadata()` 方法收集请求头。

**Validation:**
- 与 Task 2 相同的验证标准
- 支持 FastAPI/Starlette 的 request.headers 接口

**Dependencies:** Task 1

## Task 4: 修改 Markdown 报告格式 ✅

修改 `notifiers/base.py` 的 `_format_markdown()` 方法，添加请求头展示。

**Validation:**
- 当 metadata 包含 `request_headers` 时，报告显示"### 请求头"章节
- 请求头以 Markdown 列表格式展示（`- **Header-Name**: value`）
- 章节位置在"请求详情"之后，"请求参数"之前
- 当 `request_headers` 为空或不存在时，不显示该章节
- 生成的 Markdown 格式正确（无语法错误）

**Dependencies:** Task 2, Task 3

## Task 5: 更新文档和示例 ✅

更新相关文档和示例代码。

**Validation:**
- `examples/flask_demo.py` 添加请求头展示的注释说明
- `examples/fastapi_demo.py` 添加请求头展示的注释说明
- README.md 添加请求头收集功能说明 (可选)
- models.py 的 PerformanceProfile.metadata 文档字符串更新

**Dependencies:** Task 4

## Task 6: 添加单元测试 (可选)

为新功能添加单元测试。

**Validation:**
- 测试配置项的默认值和环境变量解析
- 测试 Flask 中间件的请求头收集逻辑（存在/不存在/截断/自定义列表）
- 测试 FastAPI 中间件的请求头收集逻辑
- 测试 Markdown 报告的请求头展示（存在/不存在）
- 测试 `capture_request_headers=False` 的行为
- 所有测试通过（pytest）

**Dependencies:** Task 4

## Task 7: 集成测试 (手动测试)

运行集成测试验证端到端功能。

**Validation:**
- 使用 Flask demo 应用发送带请求头的请求，验证生成的 Markdown 报告包含请求头信息
- 使用 FastAPI demo 应用发送带请求头的请求，验证生成的 Markdown 报告包含请求头信息
- 验证不同配置选项的效果
- 手动检查生成的 Markdown 文件格式正确且易读

**Dependencies:** Task 4

**建议测试命令:**
```bash
# 运行 Flask demo
python examples/flask_demo.py

# 在另一个终端测试
curl -X POST http://localhost:5000/api/submit \
     -H "Content-Type: application/json" \
     -H "X-Request-ID: test-123" \
     -H "X-Trace-ID: trace-456" \
     -d '{"order":"asc","offset":0,"limit":10}'

# 检查生成的报告
ls -lt /tmp/perf-demo/*.md | head -1
cat $(ls -t /tmp/perf-demo/*.md | head -1)
```
