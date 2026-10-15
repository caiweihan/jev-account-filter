[English](development.md) | [简体中文](development.zh-CN.md)

# 开发指南：扩展与测试

本文面向需要新增平台、扩展类别或修改代码的开发者。运行已有任务请阅读 [运行指南](commands.zh-CN.md)；类别和 API 的配置方式见 [配置说明](configuration.zh-CN.md)。

## 职责划分

| 模块 | 职责 |
| --- | --- |
| `__main__.py` | 输入、批量、进度与续跑 |
| `category.py` / `classifier.py` | 分类配置、两轮请求与答案验证 |
| `api.py` | 服务商无关的 HTTP 客户端与协议解析 |
| `platforms/douyin.py` / `platforms/kuaishou.py` | 各平台字段、作品类型与页面提取 |
| `platforms/registry.py` | 已实现平台的路由 |
| `collector.py` | 共用浏览器、登录、采集编排、状态处理与封面归档 |
| `cache.py` / `report.py` | 正式缓存与离线报告 |
| `tasks/sign_language/cover_audit.py` | 手语任务的独立封面特征检查 |

表中的路径均相对于 `account_filter/`。平台解析独立存放，共享采集器负责浏览器会话与采集编排；新增平台时需要同时接入解析器、路由和共享采集流程。

## 扩展平台

1. 在 `account_filter/platforms/` 实现该平台主页、目标作者资料与第一页作品解析。
2. 返回 `platform/url/name/bio/videos`；作品包含 `id/title/url/cover_url`，保存类型与来源证据。
3. 接入登录、空账户与风控处理，不把推荐内容当作者作品。
4. 更新路由、CLI 和输入平台映射，复用缓存与分类流程。
5. 用保存响应和本地页面验证作者、作品类型、范围与续跑行为。

扩展类别只需复制分类 TOML，不在平台适配器中写类别判断。当前流程缺乏公开视频时沿用判负，因此适合依赖视频证据的类别。

## 本地验证

`tests/` 使用本地样例和模拟响应验证采集、分类、缓存与续跑行为，不访问真实平台或付费模型。修改对应模块后运行相关测试；涉及共享流程或重构时运行完整测试集。

| 文件 | 保护的行为 |
| --- | --- |
| `test_pipeline.py` / `test_two_stage.py` | 作者过滤、第一页全集、标题先行、封面对齐及答案验证 |
| `test_post_types.py` | 图文/文章排除和类型证据恢复 |
| `test_batch.py` / `test_resume.py` / `test_reclassify.py` | CSV、成功项跳过、失败重试与离线模式 |
| `test_user_not_found.py` | 用户不存在与普通错误区别 |
| `test_cover_formats.py` | HEIC 等封面格式 |
| `test_config.py` / `test_categories.py` | API 与分类配置 |
| `test_report.py` / `test_cover_audit.py` | 报告、封面检查、空值和本地文件边界 |
| `conftest.py` | 测试缓存隔离到临时目录 |

```powershell
uv pip install --cache-dir .cache/uv --python .venv/Scripts/python.exe pytest
.\.venv\Scripts\python.exe -X utf8 -m pytest tests --basetemp=.cache/pytest-check -q
```

`pytest` 是开发依赖，日常实验不需要它。可删 `.cache/pytest-*`、`__pycache__` 等生成物，保留测试 `.py` 源文件。

## 运行入口与既有数据

命令行和测试统一使用 `account_filter`；抖音解析从 `account_filter.platforms.douyin` 导入。API 客户端统一使用 `call_model_api`，所有调用明确传协议、地址和密钥变量。CSV 列和采集缓存保持不变，新推理结果使用通用字段 `relevance_probability`，历史文件不改写。

通用报告通过类别配置中的 `report_extension` 加载专用任务组件，不根据标签或 CSV 内容自动猜任务。修改类别或模型后使用新的实验输出目录，保留历史结果及其配置快照，便于比较不同规则。
