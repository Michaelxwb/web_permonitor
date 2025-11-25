# 请求详情功能添加说明

## 修改概述

在性能监控报告（Markdown和HTML格式）中添加了"请求详情"部分，用于展示HTTP请求的关键信息。

## 修改文件

- `src/web_perfmonitor/notifiers/base.py`

## 新增内容

在Markdown和HTML报告的开头部分，紧跟基本信息之后，添加了"请求详情"部分，包含以下字段：

### Markdown格式

```markdown
### 请求详情

**URL**: http://10.74.29.68:10020/order/v1/hhw_list
**路径**: /order/v1/hhw_list
**请求方法**: POST
**请求参数**: {"order": "asc", "offset": 0, "limit": 10, "keyword": "38.38.250.207:39924", "target_company_id": [], "company_id": "28711512"}
```

### HTML格式

```html
<h3>请求详情</h3>
<ul>
  <li><strong>URL:</strong> http://10.74.29.68:10020/order/v1/hhw_list</li>
  <li><strong>路径:</strong> /order/v1/hhw_list</li>
  <li><strong>请求方法:</strong> POST</li>
  <li><strong>请求参数:</strong> {"order": "asc", "offset": 0, "limit": 10, ...}</li>
</ul>
```

## 数据来源

请求详情从`profile.metadata`中提取：

- **URL**: `metadata.get("url")`
- **路径**: `metadata.get("path")` 或 `profile.endpoint`
- **请求方法**: `metadata.get("method")` 或 `profile.method`
- **请求参数**: 合并 `query_params`、`form_data` 和 `json_body`

## 影响范围

此修改影响以下通知渠道：

1. **Email通知**: ✅ zip附件中的报告已包含请求详情
2. **Mattermost通知**: ✅ zip附件中的报告已包含请求详情
3. **Local文件保存**: ✅ markdown格式已包含请求详情

## 向后兼容性

- ✅ 完全向后兼容
- ✅ 如果metadata中没有相关字段，该部分会优雅地降级
- ✅ 所有现有测试通过（48/48）

## 测试结果

```bash
$ python3 -m pytest tests/ -v
============================== 48 passed in 2.42s ==============================
```

## 使用示例

当Flask或FastAPI应用触发性能告警时，生成的报告会自动包含请求详情部分，无需额外配置。

```python
# 示例：FastAPI应用
from web_perfmonitor import MonitorConfig, PerformanceMiddleware

config = MonitorConfig(
    threshold_seconds=0.5,
    notice_list=[{"type": "email", ...}]
)

PerformanceMiddleware(app, config=config)

# 当请求超过阈值时，报告将自动包含请求详情
```
