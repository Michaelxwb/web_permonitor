# 实现计划：Web 性能监控告警系统

**分支**: `001-flask-perf-monitor` | **日期**: 2025-11-22 | **规格**: [spec.md](./spec.md)
**输入**: 功能规格 `/specs/001-flask-perf-monitor/spec.md`

## 摘要

基于 pyinstrument 实现一个零入侵的 Python Web 应用性能监控告警系统（首期支持 Flask，架构支持扩展至 Django 等框架）。通过中间件或装饰器方式集成，
当接口响应时间超过阈值时生成性能报告并通过多种渠道（本地文件、Mattermost）异步通知。
支持 URL 白名单/黑名单过滤、告警去重、可扩展的通知渠道架构，打包为 PyPI 包便于第三方快速集成。

## 技术上下文

**语言/版本**: Python 3.8+
**主要依赖**:
- Flask >= 2.0.0（目标框架）
- pyinstrument >= 4.0.0（性能采样）
- mattermostdriver >= 7.0.0（Mattermost 通知）

**存储**: 本地文件系统（性能报告、告警记录）
**测试**: pytest + pytest-flask + pytest-asyncio
**目标平台**: 跨平台（Linux/macOS/Windows）
**项目类型**: 单项目（Python 库）
**性能目标**: 监控开销 < 5% 原响应时间，通知异步零阻塞
**约束**: < 5ms p99 新增延迟，单端点内存开销 < 50MB
**规模/范围**: 中小型 Flask 应用，支持 5+ 通知渠道并行

## 宪章检查

*门禁：必须在 Phase 0 研究前通过。Phase 1 设计后重新检查。*

| 原则 | 状态 | 验证方式 |
|------|------|----------|
| I. 零入侵原则 | ✅ 通过 | 中间件/装饰器模式，无猴子补丁，单点集成 |
| II. 性能开销限制 | ✅ 通过 | pyinstrument 采样式分析，异步通知，< 5% 开销 |
| III. 用户无感知 | ✅ 通过 | 不修改响应，错误静默处理，< 5ms p99 延迟 |
| IV. 易集成原则 | ✅ 通过 | pip install + 3 行代码，环境变量配置 |
| V. PyPI 发布标准 | ✅ 通过 | 完整元数据，类型提示，语义化版本 |

**质量门禁检查**:
- [x] mypy 严格类型检查
- [x] 核心模块测试覆盖率 > 80%
- [x] Google 风格文档字符串
- [x] ruff 代码检查零错误

## 项目结构

### 文档（本功能）

```text
specs/001-flask-perf-monitor/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出
├── data-model.md        # Phase 1 输出
├── quickstart.md        # Phase 1 输出
├── contracts/           # Phase 1 输出
└── tasks.md             # Phase 2 输出 (/speckit.tasks 命令)
```

### 源代码（仓库根目录）

```text
src/
├── web_perf_monitor/            # 核心包（框架无关）
│   ├── __init__.py              # 公共 API 导出
│   ├── py.typed                 # 类型提示标记
│   ├── config.py                # 配置管理
│   ├── profiler.py              # pyinstrument 封装
│   ├── filter.py                # URL 白名单/黑名单过滤
│   ├── alert.py                 # 告警去重逻辑
│   ├── executor.py              # 异步通知执行器
│   ├── models.py                # 数据模型
│   │
│   ├── core/                    # 核心抽象层
│   │   ├── __init__.py
│   │   ├── base_adapter.py      # 框架适配器抽象基类
│   │   ├── base_middleware.py   # 中间件抽象基类
│   │   ├── base_decorator.py    # 装饰器抽象基类
│   │   └── registry.py          # 框架注册器
│   │
│   ├── frameworks/              # 框架适配器实现
│   │   ├── __init__.py          # 框架注册和自动发现
│   │   └── flask/               # Flask 适配器
│   │       ├── __init__.py
│   │       ├── adapter.py       # FlaskAdapter 实现
│   │       ├── middleware.py    # Flask 中间件实现
│   │       └── decorator.py     # Flask 装饰器实现
│   │   # 后续扩展：
│   │   # └── django/            # Django 适配器（未来）
│   │   #     ├── __init__.py
│   │   #     ├── adapter.py
│   │   #     ├── middleware.py
│   │   #     └── decorator.py
│   │
│   └── notifiers/               # 通知器插件
│       ├── __init__.py          # 通知器注册
│       ├── base.py              # 抽象基类
│       ├── local.py             # 本地文件保存
│       └── mattermost.py        # Mattermost 通知

tests/
├── conftest.py                  # pytest 配置和 fixtures
├── unit/
│   ├── test_config.py
│   ├── test_filter.py
│   ├── test_alert.py
│   ├── test_profiler.py
│   ├── test_core/               # 核心抽象层测试
│   │   └── test_base_adapter.py
│   ├── test_frameworks/         # 框架适配器测试
│   │   └── test_flask_adapter.py
│   └── test_notifiers/
├── integration/
│   ├── test_flask_middleware.py
│   ├── test_flask_decorator.py
│   └── test_executor.py
└── performance/
    └── test_overhead.py         # 性能开销验证
```

**结构决策**:
- 采用**分层架构**，核心逻辑与框架适配分离
- `core/` 定义框架无关的抽象接口（`BaseAdapter`、`BaseMiddleware`、`BaseDecorator`）
- `frameworks/` 包含各框架的具体实现，当前仅实现 Flask，后续可扩展 Django、FastAPI 等
- 通知器使用插件架构，方便扩展新渠道
- 使用 `src/` 布局遵循 Python 打包最佳实践，便于 PyPI 发布

## 复杂性追踪

> **仅在宪章检查有需要辩护的违规时填写**

无违规，设计完全符合宪章原则。
