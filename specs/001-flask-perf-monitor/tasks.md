# 任务清单：Web 性能监控告警系统

**输入**: 设计文档 `/specs/001-flask-perf-monitor/`
**前置条件**: plan.md, spec.md, research.md, data-model.md, contracts/

**测试**: 未明确要求 - 省略测试任务。如需 TDD 方式可添加测试任务。

**组织方式**: 任务按用户故事分组，支持每个故事的独立实现和测试。

## 格式说明: `[ID] [P?] [Story] 描述`

- **[P]**: 可并行执行（不同文件，无依赖）
- **[Story]**: 所属用户故事（如 US1, US2, US3）
- 描述中包含准确的文件路径

## 路径约定

基于 plan.md 项目结构：
- 源码: `src/web_perf_monitor/`
- 测试: `tests/`

---

## 阶段 1: 项目初始化

**目的**: 项目初始化和基础结构搭建

- [x] T001 按照 plan.md 在 src/web_perf_monitor/ 创建项目目录结构
- [x] T002 初始化 Python 项目 pyproject.toml（包名: web-perf-monitor, Python 3.8+）
- [x] T003 [P] 配置依赖: Flask>=2.0.0, pyinstrument>=4.0.0, mattermostdriver>=7.0.0（可选）
- [x] T004 [P] 创建 src/web_perf_monitor/py.typed 类型提示标记文件
- [x] T005 [P] 在 pyproject.toml 中配置 ruff 代码检查
- [x] T006 [P] 在 pyproject.toml 中配置 mypy 严格模式

---

## 阶段 2: 基础设施（核心抽象 - 阻塞性）

**目的**: 必须在任何用户故事实现之前完成的核心基础设施

**⚠️ 关键**: 此阶段完成前，任何用户故事都不能开始

- [x] T007 在 src/web_perf_monitor/exceptions.py 创建异常类（WebPerfMonitorError, ConfigurationError, NotificationError, ProfilerError）
- [x] T008 [P] 在 src/web_perf_monitor/config.py 实现 MonitorConfig 数据类，包含所有字段和验证
- [x] T009 [P] 在 src/web_perf_monitor/config.py 实现 MonitorConfig.from_env() 类方法
- [x] T010 [P] 在 src/web_perf_monitor/config.py 实现 MonitorConfig.from_dict() 类方法
- [x] T011 在 src/web_perf_monitor/models.py 实现 PerformanceProfile 数据类（frozen，含 to_dict/to_json）
- [x] T012 [P] 在 src/web_perf_monitor/models.py 实现 TaskStatus 枚举
- [x] T013 [P] 在 src/web_perf_monitor/models.py 实现 NotificationTask 数据类
- [x] T014 在 src/web_perf_monitor/profiler.py 实现 Profiler 包装类（pyinstrument 集成）
- [x] T015 在 src/web_perf_monitor/core/registry.py 创建 FrameworkRegistry 单例
- [x] T016 [P] 在 src/web_perf_monitor/core/base_adapter.py 创建 BaseAdapter 抽象类（泛型：AppType, RequestType, ResponseType）
- [x] T017 [P] 在 src/web_perf_monitor/core/base_middleware.py 创建 BaseMiddleware 抽象类（含 should_profile, process_profile 具体方法）
- [x] T018 [P] 在 src/web_perf_monitor/core/base_decorator.py 创建 BaseDecorator 抽象类
- [x] T019 在 src/web_perf_monitor/notifiers/base.py 创建 BaseNotifier 抽象类
- [x] T020 [P] 在 src/web_perf_monitor/notifiers/__init__.py 实现 register_notifier 装饰器
- [x] T021 创建 src/web_perf_monitor/core/__init__.py 导出（FrameworkRegistry, BaseAdapter, BaseMiddleware, BaseDecorator）
- [x] T022 创建 src/web_perf_monitor/notifiers/__init__.py 导出（BaseNotifier, register_notifier）

**检查点**: 基础设施就绪 - 核心抽象已完成，可以开始用户故事实现

---

## 阶段 3: 用户故事 1 - 中间件快速集成 (优先级: P1) 🎯 MVP

**目标**: Flask 开发者通过添加一行中间件代码即可为所有接口启用性能监控

**独立测试**: 创建简单 Flask 应用，添加 PerformanceMiddleware，验证慢接口能正确采集性能数据

### 用户故事 1 实现

- [x] T023 [US1] 在 src/web_perf_monitor/frameworks/flask/adapter.py 实现 FlaskAdapter（通过 FrameworkRegistry 注册）
- [x] T024 [US1] 在 src/web_perf_monitor/frameworks/flask/middleware.py 实现 FlaskMiddleware（install, _before_request, _after_request）
- [x] T025 [US1] 创建 src/web_perf_monitor/frameworks/flask/__init__.py 导出
- [x] T026 [US1] 创建 src/web_perf_monitor/frameworks/__init__.py 实现 Flask 适配器自动发现
- [x] T027 [US1] 在 src/web_perf_monitor/__init__.py 实现 PerformanceMiddleware 门面类（使用 FrameworkRegistry.auto_detect）
- [x] T028 [US1] 在 FlaskMiddleware 中添加请求上下文处理（g.profiler 存储）
- [x] T029 [US1] 在 FlaskMiddleware._after_request 中实现阈值检查
- [x] T030 [US1] 确保零入侵：FlaskMiddleware 不修改响应内容/响应头/状态码
- [x] T031 [US1] 在 FlaskMiddleware 添加错误处理（捕获所有异常，记录日志但不传播）

**检查点**: 用户故事 1 完成 - 基础 Flask 中间件监控可独立工作

---

## 阶段 4: 用户故事 2 - 装饰器精准监控 (优先级: P2)

**目标**: 开发者可以使用 @profile() 装饰器监控特定函数

**独立测试**: 为函数添加 @profile()，调用时执行时间超过阈值，验证生成性能报告

### 用户故事 2 实现

- [x] T032 [US2] 在 src/web_perf_monitor/frameworks/flask/decorator.py 实现 FlaskProfileDecorator
- [x] T033 [US2] 在 FlaskProfileDecorator 中实现 _get_context（提取 Flask 请求上下文，如可用）
- [x] T034 [US2] 从 src/web_perf_monitor/frameworks/flask/__init__.py 导出 FlaskProfileDecorator
- [x] T035 [US2] 在 src/web_perf_monitor/__init__.py 实现 profile() 工厂函数
- [x] T036 [US2] 确保装饰器保留函数签名和文档字符串（functools.wraps）
- [x] T037 [US2] 确保装饰器正确处理异常（分析后重新抛出）
- [x] T038 [US2] 装饰器模式下 PerformanceProfile 的 method 字段设为 "FUNCTION"

**检查点**: 用户故事 2 完成 - @profile() 装饰器可独立工作

---

## 阶段 5: 用户故事 3 - 本地报告保存 (优先级: P3)

**目标**: 性能报告自动保存到本地文件系统

**独立测试**: 触发慢接口，验证 HTML/text 报告文件出现在配置的目录中

### 用户故事 3 实现

- [x] T039 [US3] 在 src/web_perf_monitor/notifiers/local.py 实现 LocalNotifier
- [x] T040 [US3] 在 LocalNotifier 中实现报告文件命名规范（{endpoint_safe}_{timestamp}_{id}.html/.txt）
- [x] T041 [US3] 在 LocalNotifier 中实现目录不存在时自动创建
- [x] T042 [US3] 在 LocalNotifier 中实现 markdown 格式报告生成
- [x] T043 [US3] 在 LocalNotifier 中实现 text 格式报告生成
- [x] T044 [US3] 使用 @register_notifier("local") 注册 LocalNotifier
- [x] T045 [US3] 在 LocalNotifier 中实现 validate_config
- [x] T046 [US3] 在 LocalNotifier 中优雅处理磁盘空间错误（记录日志，不崩溃）

**检查点**: 用户故事 3 完成 - 本地文件保存可独立工作

---

## 阶段 6: 用户故事 4 - Mattermost 消息通知 (优先级: P4)

**目标**: 性能告警实时推送到 Mattermost 频道

**独立测试**: 配置 Mattermost 连接信息，触发告警，验证消息出现在指定频道

### 用户故事 4 实现

- [x] T047 [US4] 在 src/web_perf_monitor/notifiers/mattermost.py 实现 MattermostNotifier
- [x] T048 [US4] 在 MattermostNotifier 中使用 mattermostdriver 实现 Mattermost API 集成
- [x] T049 [US4] 实现 Mattermost markdown 格式消息
- [x] T050 [US4] 实现 Mattermost text 格式消息
- [x] T051 [US4] 在 MattermostNotifier 中实现 validate_config（检查 server_url, token, channel_id）
- [x] T052 [US4] 使用 @register_notifier("mattermost") 注册 MattermostNotifier
- [x] T053 [US4] 优雅处理网络错误（记录日志，不崩溃）
- [x] T054 [US4] 通知消息中包含接口路径、响应时间、性能摘要

**检查点**: 用户故事 4 完成 - Mattermost 通知可独立工作

---

## 阶段 7: 用户故事 5 - 告警去重 (优先级: P5)

**目标**: 同一接口在配置的时间窗口内不会重复告警

**独立测试**: 多次触发同一慢接口，验证只发送第一次告警

### 用户故事 5 实现

- [x] T055 [US5] 在 src/web_perf_monitor/models.py 实现 AlertRecord 数据类
- [x] T056 [US5] 在 src/web_perf_monitor/alert.py 实现 AlertManager
- [x] T057 [US5] 在 AlertManager 中实现 should_alert(endpoint) 方法（检查时间窗口）
- [x] T058 [US5] 在 AlertManager 中实现 record_alert(endpoint) 方法
- [x] T059 [US5] 在 AlertManager 中实现 alerts.json 文件持久化
- [x] T060 [US5] 在 AlertManager 中实现内存缓存与文件同步
- [x] T061 [US5] 将 AlertManager 集成到 BaseMiddleware.process_profile
- [x] T062 [US5] 优雅处理损坏的 alerts.json（重置为空）

**检查点**: 用户故事 5 完成 - 告警去重可独立工作

---

## 阶段 8: 用户故事 6 - URL 过滤控制 (优先级: P6)

**目标**: 开发者可配置白名单/黑名单控制监控哪些 URL

**独立测试**: 配置白名单/黑名单，访问不同 URL，验证过滤行为正确

### 用户故事 6 实现

- [x] T063 [US6] 在 src/web_perf_monitor/filter.py 实现 UrlFilter 类
- [x] T064 [US6] 在 UrlFilter 中实现精确匹配逻辑（如 "/api/users"）
- [x] T065 [US6] 在 UrlFilter 中使用 fnmatch 实现通配符匹配逻辑（如 "/api/*"）
- [x] T066 [US6] 实现白名单优先规则（设置白名单时忽略黑名单）
- [x] T067 [US6] 在 UrlFilter 中实现 should_monitor(path) 方法
- [x] T068 [US6] 将 UrlFilter 集成到 BaseMiddleware.should_profile
- [x] T069 [US6] 优雅处理无效匹配模式格式（记录警告，跳过该模式）

**检查点**: 用户故事 6 完成 - URL 过滤可独立工作

---

## 阶段 9: 用户故事 7 - PyPI 包安装 (优先级: P7)

**目标**: 可通过 pip install web-perf-monitor 安装包

**独立测试**: 构建包，在干净的虚拟环境中安装，导入并验证功能

### 用户故事 7 实现

- [x] T070 [US7] 完善 pyproject.toml 元数据（description, authors, license, classifiers）
- [x] T071 [US7] 在 pyproject.toml 配置可选依赖 [mattermost]
- [x] T072 [US7] 在 src/web_perf_monitor/__init__.py 导出公共 API（PerformanceMiddleware, profile, MonitorConfig, PerformanceProfile）
- [x] T073 [US7] 在 src/web_perf_monitor/__init__.py 添加版本号 __version__
- [x] T074 [US7] 创建 README.md 包含快速入门文档
- [x] T075 [US7] 创建 CHANGELOG.md 记录 0.1.0 版本
- [ ] T076 [US7] 验证包使用 python -m build 构建成功
- [ ] T077 [US7] 验证包在干净环境中安装正确

**检查点**: 用户故事 7 完成 - 包准备好发布到 PyPI

---

## 阶段 10: 异步通知执行（跨故事）

**目的**: 实现异步并行通知执行，确保零阻塞

- [x] T078 在 src/web_perf_monitor/executor.py 实现 NotificationExecutor（基于 ThreadPoolExecutor）
- [x] T079 在 NotificationExecutor 中实现 submit(profile) 方法（创建 NotificationTask，提交到线程池）
- [x] T080 在 NotificationExecutor 中实现并行通知分发（所有通知器并发执行）
- [x] T081 在 NotificationExecutor 中实现每个通知器的超时控制
- [x] T082 在 NotificationExecutor 中实现任务队列大小限制（满时丢弃最旧任务）
- [x] T083 在 NotificationExecutor 中实现 shutdown(timeout) 方法（优雅关闭）
- [x] T084 将 NotificationExecutor 集成到 BaseMiddleware
- [x] T085 为 PerformanceMiddleware.shutdown() 添加关闭钩子

---

## 阶段 11: 收尾与跨故事优化

**目的**: 影响多个用户故事的最终改进

- [x] T086 [P] 在所有模块中添加完整的日志记录
- [x] T087 [P] 为所有公共 API 添加类型提示
- [ ] T088 运行 mypy 严格类型检查，修复所有错误
- [ ] T089 运行 ruff 代码检查，修复所有错误
- [x] T090 [P] 为所有公共类和方法添加 Google 风格文档字符串
- [ ] T091 验证 quickstart.md 场景端到端可用
- [ ] T092 性能验证：确认监控请求开销 < 5%
- [x] T093 在 examples/flask_demo.py 创建示例 Flask 应用

---

## 依赖关系与执行顺序

### 阶段依赖

- **初始化（阶段 1）**: 无依赖 - 可立即开始
- **基础设施（阶段 2）**: 依赖初始化完成 - 阻塞所有用户故事
- **用户故事（阶段 3-9）**: 全部依赖基础设施阶段完成
  - 用户故事可并行进行（如有人力）
  - 或按优先级顺序执行（P1 → P2 → P3 → P4 → P5 → P6 → P7）
- **异步执行（阶段 10）**: 阶段 2 后可开始，应在阶段 11 前完成
- **收尾（阶段 11）**: 依赖所有用户故事完成

### 用户故事依赖

| 用户故事 | 依赖 | 说明 |
|----------|------|------|
| US1 (P1) | 基础设施 | MVP - 不依赖其他故事 |
| US2 (P2) | 基础设施 | 独立于 US1，共享基础装饰器 |
| US3 (P3) | 基础设施 | 独立，实现 LocalNotifier |
| US4 (P4) | 基础设施 | 独立，实现 MattermostNotifier |
| US5 (P5) | 基础设施 | 独立，AlertManager 被 BaseMiddleware 使用 |
| US6 (P6) | 基础设施 | 独立，UrlFilter 被 BaseMiddleware 使用 |
| US7 (P7) | 所有故事 | 包组装，依赖所有功能 |

### 单个用户故事内部顺序

- 先实现模型/实体
- 再实现服务/管理器
- 然后实现框架特定代码
- 最后处理集成和错误处理

### 并行机会

- 所有标记 [P] 的初始化任务可并行执行
- 所有标记 [P] 的基础设施任务可并行执行（阶段 2 内部）
- 基础设施阶段完成后：
  - US1, US2, US3, US4, US5, US6 可全部并行开始
  - US7 应等待其他故事提供打包内容
- 阶段 10（异步）可与 US3-US6 并行进行

---

## 并行示例：基础设施阶段

```bash
# 同时启动所有 [P] 基础设施任务：
任务: "在 src/web_perf_monitor/config.py 实现 MonitorConfig 数据类"
任务: "在 src/web_perf_monitor/config.py 实现 MonitorConfig.from_env()"
任务: "在 src/web_perf_monitor/config.py 实现 MonitorConfig.from_dict()"
任务: "在 src/web_perf_monitor/core/base_adapter.py 创建 BaseAdapter 抽象类"
任务: "在 src/web_perf_monitor/core/base_middleware.py 创建 BaseMiddleware 抽象类"
任务: "在 src/web_perf_monitor/core/base_decorator.py 创建 BaseDecorator 抽象类"
```

## 并行示例：基础设施完成后的用户故事

```bash
# 阶段 2 完成后多开发者并行：
开发者 A: US1（中间件）+ US2（装饰器）
开发者 B: US3（本地保存）+ US4（Mattermost）
开发者 C: US5（告警去重）+ US6（URL 过滤）
# 然后: 所有人一起完成 US7（PyPI 包）
```

---

## 实现策略

### MVP 优先（仅用户故事 1）

1. 完成阶段 1: 初始化
2. 完成阶段 2: 基础设施（关键 - 阻塞所有故事）
3. 完成阶段 3: 用户故事 1（中间件）
4. **停下来验证**: 独立测试 Flask 中间件
5. 如果就绪可部署/演示 - 基础监控已可用！

### 增量交付

1. 初始化 + 基础设施 → 基础就绪
2. 添加 US1（中间件）→ 测试 → 部署（MVP！）
3. 添加 US2（装饰器）→ 测试 → 部署
4. 添加 US3（本地保存）+ US4（Mattermost）→ 测试 → 部署（完整通知功能）
5. 添加 US5（告警去重）→ 测试 → 部署
6. 添加 US6（URL 过滤）→ 测试 → 部署
7. 添加 US7（PyPI 包）→ 测试 → 发布

### 建议 MVP 范围

**MVP = 阶段 1 + 阶段 2 + 阶段 3（用户故事 1）**

交付内容：
- Flask 中间件集成
- 基于 pyinstrument 的性能采样
- 阈值触发报告生成
- 基础 PerformanceProfile 创建

价值：开发者可以用一行代码立即监控 Flask 应用性能。

---

## 统计摘要

| 类别 | 数量 |
|------|------|
| 总任务数 | 93 |
| 初始化任务 | 6 |
| 基础设施任务 | 16 |
| US1 任务 | 9 |
| US2 任务 | 7 |
| US3 任务 | 8 |
| US4 任务 | 8 |
| US5 任务 | 8 |
| US6 任务 | 7 |
| US7 任务 | 8 |
| 异步执行任务 | 8 |
| 收尾任务 | 8 |
| 可并行机会 | 25+ 个 [P] 标记 |

---

## 注意事项

- [P] 任务 = 不同文件，不依赖未完成的任务
- [Story] 标签将任务映射到特定用户故事以便追踪
- 每个用户故事应可独立完成和测试
- 每个任务或逻辑组完成后提交代码
- 在任何检查点可停下来独立验证故事
- 未包含测试任务 - 如需 TDD 方式可添加
