# Project Context

## Purpose

Web Performance Monitor (web-perfmonitor) 是一个轻量级的 Python Web 框架性能监控库，基于 pyinstrument 构建。项目目标是提供零侵入式的性能监控能力，支持自动性能分析、智能告警去重和多渠道通知。

### 核心价值
- **零侵入式监控** - 无需修改应用代码即可添加性能监控
- **自动性能分析** - 当响应时间超过阈值时自动捕获详细的调用栈
- **智能告警去重** - 基于时间窗口的告警去重，防止告警风暴
- **多渠道通知** - 支持本地文件、Mattermost、邮件等多种通知方式
- **低开销** - 基于 pyinstrument 的采样分析器，性能开销极低

## Tech Stack

### 核心依赖
- **Python** >= 3.8 (支持 3.8, 3.9, 3.10, 3.11, 3.12)
- **Flask** >= 2.0.0 (当前支持的 Web 框架)
- **pyinstrument** >= 4.0.0 (性能分析核心)

### 可选依赖
- **mattermostdriver** >= 7.0.0 (Mattermost 通知支持)

### 开发依赖
- **pytest** >= 7.0.0 (测试框架)
- **pytest-flask** >= 1.2.0 (Flask 测试集成)
- **pytest-asyncio** >= 0.21.0 (异步测试支持)
- **mypy** >= 1.0.0 (类型检查)
- **ruff** >= 0.1.0 (代码检查和格式化)
- **build** >= 1.0.0 (打包构建)

## Project Conventions

### Code Style

- **代码检查**: 使用 ruff 进行代码检查，启用规则: E, W, F, I, B, C4, UP
- **类型检查**: 使用 mypy strict 模式，所有公共 API 必须有完整的类型注解
- **行长度限制**: 100 字符
- **目标 Python 版本**: 3.8+
- **文档字符串**: 使用 Google 风格的 docstring
- **命名规范**:
  - 类名: PascalCase (如 `MonitorConfig`, `AlertManager`)
  - 函数/方法: snake_case (如 `should_alert`, `create_profile`)
  - 常量: UPPER_SNAKE_CASE (如 `DEFAULT_THRESHOLD`)
  - 私有成员: 单下划线前缀 (如 `_executor`, `_lock`)

### Architecture Patterns

#### 模块化插件架构
项目采用插件式架构设计，便于扩展：

1. **框架适配器模式** (`core/`)
   - `FrameworkRegistry`: 单例模式，管理框架适配器注册
   - `BaseAdapter`: 框架适配器基类
   - `BaseMiddleware`: 中间件基类
   - `BaseDecorator`: 装饰器基类
   - 使用 `@FrameworkRegistry.register("framework_name")` 装饰器注册新适配器

2. **通知器模式** (`notifiers/`)
   - `BaseNotifier`: 通知器抽象基类
   - 使用 `@register_notifier("notifier_type")` 装饰器注册新通知器
   - 必须实现 `send()` 和 `validate_config()` 方法

3. **数据类模式** (`models.py`)
   - 使用 `@dataclass(frozen=True)` 定义不可变数据模型
   - 所有模型支持 JSON 序列化

#### 线程安全
- `AlertManager` 使用 `threading.Lock` 保证线程安全
- `NotificationExecutor` 使用 `ThreadPoolExecutor` 进行异步通知
- Flask 中间件使用 `flask.g` 存储请求级别状态

#### 配置层次
配置支持多种来源，优先级从高到低：
1. 代码直接传参
2. 环境变量 (前缀 `PERF_`)
3. 默认值

### Testing Strategy

#### 测试目录结构
```
tests/
├── unit/           # 单元测试
├── integration/    # 集成测试
└── performance/    # 性能测试
```

#### 测试要求
- 新功能必须包含对应的单元测试
- 集成测试覆盖主要使用场景
- 使用 `pytest` 作为测试框架
- 使用 `pytest-flask` 进行 Flask 应用测试
- 使用 `pytest-asyncio` 进行异步代码测试

#### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定目录测试
pytest tests/unit/

# 带覆盖率报告
pytest --cov=web_perfmonitor
```

### Git Workflow

#### 分支策略
- `main`: 主分支，保持稳定可发布状态
- `feature/*`: 功能开发分支
- `fix/*`: Bug 修复分支
- `docs/*`: 文档更新分支

#### 提交规范
使用语义化提交信息：
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具相关

## Domain Context

### 性能监控领域概念

- **阈值 (Threshold)**: 触发性能分析的响应时间临界值，默认 1.0 秒
- **性能剖析 (Profile)**: pyinstrument 生成的调用栈分析结果
- **告警窗口 (Alert Window)**: 同一端点的告警去重时间窗口，默认 10 天
- **端点 (Endpoint)**: Web 请求的 URL 路径 + HTTP 方法组合
- **通知器 (Notifier)**: 告警发送渠道的抽象

### 核心业务流程

```
请求进入 → URL过滤 → 启动分析器 → 处理请求 → 停止分析器
                                            ↓
                               响应时间 > 阈值?
                                    ↓ 是
                               告警去重检查
                                    ↓ 需要告警
                               生成报告 → 本地保存
                                    ↓
                               异步发送通知
```

### 关键文件路径

| 模块 | 文件路径 | 主要功能 |
|------|---------|---------|
| 配置 | `src/web_perfmonitor/config.py` | MonitorConfig、环境变量支持 |
| API入口 | `src/web_perfmonitor/__init__.py` | 公共API导出 |
| 分析器 | `src/web_perfmonitor/profiler.py` | pyinstrument包装 |
| 告警 | `src/web_perfmonitor/alert.py` | 去重管理、JSON持久化 |
| 过滤 | `src/web_perfmonitor/filter.py` | URL Glob模式匹配 |
| 执行器 | `src/web_perfmonitor/executor.py` | 异步通知、线程池 |
| Flask中间件 | `src/web_perfmonitor/frameworks/flask/middleware.py` | before/after_request钩子 |
| 通知基类 | `src/web_perfmonitor/notifiers/base.py` | 基础通知器、格式化 |
| 本地通知 | `src/web_perfmonitor/notifiers/local.py` | 文件保存 |
| 示例应用 | `examples/flask_demo.py` | Flask演示 |

## Important Constraints

### 技术约束
- **Python 版本**: 必须兼容 Python 3.8+
- **性能开销**: 分析器开销不得超过请求时间的 5%
- **线程安全**: 所有共享状态必须线程安全
- **异步通知**: 通知发送不得阻塞请求处理

### 设计约束
- **零侵入**: 用户只需一行代码即可启用监控
- **可扩展**: 新框架和通知渠道可通过插件方式添加
- **向后兼容**: 公共 API 变更需要遵循语义化版本

### 安全约束
- 不记录敏感信息（密码、Token 等）
- 通知内容中不包含请求体中的敏感数据
- 本地报告文件权限应适当限制

## External Dependencies

### pyinstrument
- **用途**: 核心性能分析器
- **文档**: https://github.com/joerick/pyinstrument
- **集成方式**: `Profiler` 类封装

### Flask
- **用途**: 当前支持的 Web 框架
- **文档**: https://flask.palletsprojects.com/
- **集成方式**: `FlaskMiddleware` 通过 `before_request` 和 `after_request` 钩子

### Mattermost (可选)
- **用途**: 团队协作通知
- **文档**: https://api.mattermost.com/
- **集成方式**: `MattermostNotifier` 使用 `mattermostdriver` SDK

## Project Structure

```text
web_permonitor/
├── src/web_perfmonitor/          # 源代码主目录
│   ├── __init__.py              # 公共API导出
│   ├── config.py                # 配置管理
│   ├── models.py                # 数据模型
│   ├── profiler.py              # 性能分析器包装
│   ├── executor.py              # 异步通知执行器
│   ├── alert.py                 # 告警去重管理
│   ├── filter.py                # URL过滤
│   ├── exceptions.py            # 自定义异常
│   ├── core/                    # 框架适配核心
│   │   ├── registry.py          # 框架注册表
│   │   ├── base_adapter.py      # 适配器基类
│   │   ├── base_middleware.py   # 中间件基类
│   │   └── base_decorator.py    # 装饰器基类
│   ├── frameworks/              # 框架特定实现
│   │   └── flask/
│   │       ├── adapter.py       # Flask适配器
│   │       ├── middleware.py    # Flask中间件
│   │       └── decorator.py     # Flask装饰器
│   └── notifiers/               # 通知系统
│       ├── base.py              # 基础通知器
│       ├── local.py             # 本地文件保存
│       ├── mattermost.py        # Mattermost集成
│       └── email.py             # 邮件通知
├── examples/                    # 示例代码
│   └── flask_demo.py            # Flask演示应用
├── tests/                       # 测试代码
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   └── performance/             # 性能测试
├── specs/                       # 功能规范文档
├── openspec/                    # OpenSpec变更管理
├── pyproject.toml               # 项目配置
├── README.md                    # 英文文档
├── README_CN.md                 # 中文文档
└── CHANGELOG.md                 # 更新日志
```

## Commands

### 开发命令
```bash
# 安装开发依赖
pip install -e ".[dev]"

# 代码检查
ruff check src/

# 类型检查
mypy src/

# 运行测试
pytest

# 构建包
python -m build
```

### 示例运行
```bash
# 运行 Flask 演示
python examples/flask_demo.py

# 访问演示端点
curl http://localhost:5000/
curl http://localhost:5000/slow
curl http://localhost:5000/api/data
```

## Public API Reference

### 主要导出
```python
from web_perfmonitor import (
    PerformanceMiddleware,      # 中间件类
    MonitorConfig,              # 配置类
    profile,                    # 函数装饰器
    PerformanceProfile,         # 性能数据模型
    get_config, set_config,     # 全局配置管理
    WebPerfMonitorError,        # 基础异常
    ConfigurationError,         # 配置错误
    NotificationError,          # 通知错误
    ProfilerError,              # 分析器错误
)
```

### 快速开始
```python
from flask import Flask
from web_perfmonitor import PerformanceMiddleware, MonitorConfig

app = Flask(__name__)

# 最简配置
PerformanceMiddleware(app)

# 或者自定义配置
config = MonitorConfig(
    threshold_seconds=0.5,
    alert_window_days=7,
    log_path="/var/log/myapp",
    url_whitelist=["/api/*"],
    notice_list=[
        {
            "type": "mattermost",
            "server_url": "https://mm.example.com",
            "token": "xxx",
            "channel_id": "yyy"
        }
    ]
)
PerformanceMiddleware(app, config=config)
```

## Version History

### v0.1.0 (2025-11-22) - Alpha
- 核心框架实现（PerformanceMiddleware、profile装饰器）
- 配置系统（MonitorConfig + 环境变量支持）
- 性能分析（Profiler包装）
- 告警去重（AlertManager）
- URL过滤（UrlFilter）
- 框架适配（FrameworkRegistry、FlaskAdapter）
- 通知系统（LocalNotifier、MattermostNotifier、EmailNotifier）
- 异步执行（NotificationExecutor）

### 计划功能
- Django 框架支持
- FastAPI 框架支持
- Prometheus metrics 导出
- Web 仪表板（报告查看）
