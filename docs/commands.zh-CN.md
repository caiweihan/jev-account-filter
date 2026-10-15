[English](commands.md) | [简体中文](commands.zh-CN.md)

# 运行指南

在项目根目录的 PowerShell 执行。分类必须明确选择 `--config` 和 `--category`，程序不预设服务商或目标类别。

## 新分类实验

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --top-videos 5 --output output/my-experiment
.\.venv\Scripts\python.exe -X utf8 -m account_filter run "真实频道主页链接" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml"
```

配置文件需先准备，见 [配置说明](configuration.zh-CN.md)。`--platform auto` 按链接识别，可混合抖音和快手，也可指定 `douyin` 或 `kuaishou`。平台识别与分类类别无关。

输入 CSV 必需 `主页网址`；可选 `平台`、`账户昵称`、`人工标注`，兼容 `审核结果` 与 `真实标签`。正负标签由类别配置定义，也接受 `1/0/-1`。人工标注只用于事后对照。

公开格式样例见 [`input/channels.example.csv`](../input/channels.example.csv)。其中所有账号均为虚构，运行前请替换主页链接；团队真实输入文件不随仓库公开。

## 只读缓存的新实验

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --from-cache --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --output output/new-experiment
```

不访问平台或封面 CDN，仍调用明确选定的模型。新实验不复用旧模型答案。

## 一个具体示例：手语任务

这条命令明确选择已有服务配置和手语规则，不代表项目默认值：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --config configs/api.toml --category sign-language --top-videos 5 --output output/sign-language-next
```

## 续跑

新实验保存 `category.json`、`api-config.json`。有这些快照时无需再次输入选择：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/实验/时间目录"
```

读取的是这次实验已经明确选定的配置，而非系统默认。缺少快照的旧实验需显式提供：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/douyin-v7/20261014-113151-009297" --config configs/api.toml --category sign-language --top-videos 5
```

跳过成功项，重试失败与未完成项，更新同一个 CSV。更换目标类别须创建新实验。

## 只采集 / 更新缓存

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter collect "真实频道主页链接"
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --refresh-cache --login-timeout 600 --output output/cache-refresh
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/cache-refresh/实际时间目录"
```

只采集时不需要模型或类别配置，不调用 API。新浏览器会话在 `.browser/profile/`；复用旧会话时显式加 `--browser-dir .browser/kuaishou`。

## 可视化

直接用 Edge 或 Chrome 打开项目根目录的 [`analysis.html`](../analysis.html)，无需启动服务或运行 Python：

1. 选择实验的 `results.csv`。编码自动检测，分析类别从已配置的标签或匹配实验配置中识别；通常无需其他操作。无法唯一识别时才在“分析设置”中选择类别或指定自定义正负标签。
2. 可选“添加缓存文件夹”：选择 `data/channels/` 或其它位置的同结构缓存，可显示简介、候选标题和封面。
3. 需要第一轮标题分数、原实验快照或已有独立封面审核时，再添加该实验的整个时间目录。可分次添加多个文件夹。匹配的实验目录含 `category.json` 时，尚未选择的类别会自动恢复。
4. 切换 CSV 即可分析另一次实验；修改 CSV 后重新选择。每次载入会重置图表的筛选状态。
5. 可选载入“二次核验 CSV”，在同一套准确率、混淆矩阵、错误分布和账户明细中比较原人工标注与模型预测；清除后回到原标注一致性对照。

选择后默认记住结果 CSV、核验 CSV、多个缓存目录，以及类别和编码，并在浏览器中保存上次分析及实际使用的封面。重新打开同一个 HTML 就直接显示上次分析，无需点击恢复按钮；有读取权限时自动载入最新文件，权限过期时显示带缓存时间的上次分析。只有需要同步磁盘上的新改动时，才使用“更新本地文件”并按浏览器要求授权。“忘记上次选择”删除保存的选择与浏览器分析副本，当前分析保留。

文件位置自动重读需要支持文件系统访问接口的 Edge / Chrome；分析副本恢复需要可用且空间足够的浏览器本地存储。只缓存本次分析用到的数据和封面，不复制整个缓存目录，也不上传或写进 HTML。请用同一浏览器和同一 HTML 路径打开；隐私模式、清除浏览器数据会使记忆失效。不支持文件句柄时回退到普通文件选择，仍可恢复已保存的分析；重新读取更新后的磁盘文件需要重新选择。

直接打开本地 `analysis.html`（`file://`）默认使用普通文件选择，避免浏览器虽提供原生选择器却拒绝 `getFile()` 的情况；旧版本保存的原生句柄不会在此模式下重读。上次分析、二次核验和所用封面仍自动恢复，磁盘文件有新改动时重新选择即可。通过网页地址打开时，若原生读取被拒绝，也会显示普通文件选择并保留现有分析。目录中个别文件不可读时跳过并提示，不让整个目录载入失败。

文件区随整页滚动，目录添加后持续显示目录名，不依赖原生选择框的临时文件名。类别与编码设置默认折叠；自动编码依次尝试 UTF-8、GB18030，并识别带 BOM 的 UTF-16。手动设置仅作覆盖或排错，不修改输入文件。

页面先展示原人工类别与模型预测类别的全量占比，空标注、疑难和非类别预测分别列示。随后统一展示分类性能、分数分布、特征聚类、错误类型和账户证据。

聚类使用预测类别与视频 1–5 的五条分数：类别独热编码使不同类别的平方距离为 1，分数保持 0–1 尺度。确定性 K-means 默认 5 组，可选 2–8 组；实际组数不超过不同特征向量的数量。仅完整五分数且预测有效的账户参与，缺失不补零。PCA 只用于二维展示，不参与聚类；图中给出解释方差，重叠点可从聚类表筛选。聚类不使用人工标注，也不改变模型结果。

二次核验支持与审核表一致的 `平台,账户id,账户昵称,主页网址,审核结果` 格式；最低需要 `主页网址,审核结果`，也接受 `频道网址` 和 `二次标注` / `人工标注` 列名。只提供账户id时，结果 CSV 本身也必须包含账户id。数值标签 `1/0/-1` 分别按当前类别映射为正类、疑难、负类。核验编码独立自动检测，也可在设置中覆盖。

载入有效二次核验后，默认在已复核的共同样本上比较准确率：原标注与二次标签一致的比例为人工准确率，模型与二次标签一致的比例为模型准确率。分母要求参考标签、原标注及预测均为当前有效标签。可按参考类别、特征聚类、最高视频分数区间比较两者的组内错误率，并直接筛选人工错误、模型错误和两者均错误的账户。两类错误可以重叠。原标注、二次标注和模型结果在同一明细中并列保留。

“评估参考”可切换原标注全量一致性、二次核验子集准确率、二次标签覆盖后的全量条件估计。最后一种沿用未复核原标注，假设这些标注正确；不可当作独立验证的全量准确率。若只复核原不符项，子集结论也不能外推到全量。冲突、未知标签和非唯一匹配输入在“评估方法与数据质量”中列明；切换 CSV 重新匹配，不沿用行号。旧任务专属规则模拟仍沿用原标注，标题和说明标明这一范围。所有切换只影响展示，不写回原始结果。

文件只在本地浏览器中读取，不上传、不访问平台或模型、不修改 CSV 或缓存。浏览器只允许读取你主动选择的目录；只选实验目录时，目录外的正式缓存封面仍需单独选择。缓存按频道和视频链接匹配，重名封面存在歧义时显示缺失。缺少缓存不影响 CSV 统计；简介、标题、封面和第一轮分数不会从 CSV 猜测。CSV 支持 UTF-8 与 GB18030 / GBK 编码。

`analysis.html` 已随项目提供，内部不包含实验数据。修改分类配置或报告模板后，可一次性重新打包页面，之后仍可反复选择不同 CSV：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.viewer
```

旧的命令仍可用于导出包含固定结果数据的 HTML 快照：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/实验/时间目录/results.csv"
```

分类标签从本实验的 `category.json` 读取。如果旧实验无快照，需要 `--category`，例如：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/douyin-v7/20261014-113151-009297/results.csv" --category sign-language
```

生成同目录 HTML，不修改 CSV，不访问平台或模型。仅当类别配置明确启用报告扩展时，才附加其专用分析区。

## 可选的手语封面审核工具

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "结果CSV路径" --config configs/api.toml
```

这是单独的任务工具，会调用明确选定的模型；不属于通用分类入口的默认流程。
