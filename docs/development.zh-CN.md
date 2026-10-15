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
| `test_viewer.py` | 浏览器 CSV 读取、跨目录封面对齐、类别恢复、重复载入和文本转义 |
| `test_second_review.py` | 数据集分布、二次标注匹配、固定分母、冲突处理及复核后筛选 |
| `conftest.py` | 测试缓存隔离到临时目录 |

```powershell
uv pip install --cache-dir .cache/uv --python .venv/Scripts/python.exe pytest
.\.venv\Scripts\python.exe -X utf8 -m pytest tests --basetemp=.cache/pytest-check -q
```

`pytest` 是开发依赖，日常实验不需要它。可删 `.cache/pytest-*`、`__pycache__` 等生成物，保留测试 `.py` 源文件。

## 运行入口与既有数据

命令行和测试统一使用 `account_filter`；抖音解析从 `account_filter.platforms.douyin` 导入。API 客户端统一使用 `call_model_api`，所有调用明确传协议、地址和密钥变量。CSV 列和采集缓存保持不变，新推理结果使用通用字段 `relevance_probability`，历史文件不改写。

通用报告通过类别配置中的 `report_extension` 加载专用任务组件，不根据标签或 CSV 内容自动猜任务。修改类别或模型后使用新的实验输出目录，保留历史结果及其配置快照，便于比较不同规则。

## 浏览器分析页面

根目录 `analysis.html` 是不含实验数据的离线查看器。`account_filter/viewer.py` 将现有通用报告和显式配置的任务扩展打包，外层界面与读取逻辑位于 `templates/viewer.html` 和 `templates/viewer.js`。图表及任务模拟继续使用原报告组件；CSV 解析和汇总在浏览器完成，测试会与 Python 汇总结果对照。

修改报告组件、查看器或类别配置后，运行 `python -m account_filter.viewer` 同步根目录 HTML。日常切换 CSV 无需重建。缓存通过用户选择的 `File` 对象读取；只为实际展示的候选传递本地封面，隔离的报告页面自行创建 Blob URL，不下载远程图片。新增缓存类型时保留按频道、视频 URL 匹配的逻辑，避免按 CSV 行号或目录顺序对齐。

`templates/analysis-extra.js` 提供标签和复核共享函数；`analysis-evaluation.js` 按当前参考口径派生展示行，统一驱动性能、分布、错误特征和账户明细，保持原 `D.rows` 不变。`analysis-cluster.js` 对五个完整分数和预测独热特征使用确定性最远点初始化的 K-means，不使用人工标签；PCA 仅用于投影展示。空数据、重复特征和缺失分数均显式处理。`test_dashboard.py` 检查聚类确定性、预测类别作用、标注隔离、评估分母、错误筛选、自动设置和整页滚动。

评估参考分别表示原标注一致性、已复核共同样本准确率、全量条件估计。人工和模型使用同一有效样本；未复核项沿用原标注时必须注明条件，不能称为独立全量验证。`viewer.js` 仍按唯一身份匹配核验，冲突保留在 `second_review`。静态报告复用这些分析组件，但不自动读取另一份 CSV。

隔离报告通过带每次渲染令牌、校验窗口来源的消息向外层报告正文高度，实现整页单一滚动，保持沙箱隔离。浏览器查看器的证据在正文展开，静态导出保留原生弹窗。类别只匹配配置标签或精确匹配的实验快照，不猜未知类别的正类；编码严格尝试 UTF-8/GB18030 并识别 UTF-16 BOM。歧义类别及手动覆盖保留在折叠设置中，已选文件与目录名称通过文本节点展示，不依赖原生选择框状态。

`templates/viewer-session.js` 在 IndexedDB 中按 HTML 路径保存只读文件、目录句柄、界面选择和上次分析。分析副本包含输入数据及实际引用的候选、封面核验资源，保存前精简资源 ID。打开页面无需点击即可展示副本，仅查询磁盘读取权限；主动更新时才可能申请授权。权限有效则重读最新文件，权限缺失时按频道和视频 URL 匹配已缓存证据，并标明缓存时间。忘记选择同时删除句柄和分析副本；存储失败不影响当前分析。`test_viewer_session.py` 检查虚构数据的恢复、缓存图片解码、权限过期、文件更新、清除和存储回退。保留报告隔离沙箱和离线 CSP。

`file://` 使用普通文件输入和分析副本恢复，不尝试重读旧原生句柄。原生模式同时捕获选择器和 `getFile()` 的 `NotAllowedError`、`SecurityError` 等拒绝，提供普通选择回退，避免仅依赖 `queryPermission()` 的结果。目录枚举仅获取 JSON、CSV 和图片；每个读取 Promise 立即接住拒绝，跳过不可读条目并报告缺失。测试覆盖权限查询通过但实际读取失败、旧句柄迁移和受限目录条目。
