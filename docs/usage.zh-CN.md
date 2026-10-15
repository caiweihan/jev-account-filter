[English](usage.md) | [简体中文](usage.zh-CN.md)

# 手语实验说明与历史记录

本文保留原手语任务的详细流程和实验记录；下述配置是明确选择的手语实验示例，不是通用程序默认值。项目现已整理为 Jev Account Filter，命令统一使用 `account_filter`。安装、当前命令和可选配置分别见 [安装](installation.zh-CN.md)、[运行指南](commands.zh-CN.md)、[配置说明](configuration.zh-CN.md)。

支持快手、抖音主页链接。目标是**手语频道**：个人账号可凭一两个可信手语视频判正；名称与简介显示无关地方媒体、娱乐新闻等的账号采用更严格的频道定位判据，不能仅凭偶发一个手语视频判正。明确手语或手语无障碍主题的媒体账号仍可判正。**本任务中手语舞一定按手语处理，手势舞不是手语**。项目保持为小型 Python 命令行工具；环境、浏览器会话和缓存都在项目内。

## 运行

```powershell
cd path\to\jev-account-filter
.\.venv\Scripts\python.exe -m account_filter run 'https://www.kuaishou.com/profile/EXAMPLE_KUAISHOU_ACCOUNT_B' --top-videos 5 --output output/my-channel --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音测试3.csv --top-videos 5 --output output/douyin-test --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音实验25.csv --top-videos 5 --output output/douyin-experiment --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音全部频道.csv --top-videos 5 --login-timeout 600 --output output/douyin-all --config configs/api.toml --category sign-language
```

依赖在 `.venv/` 中；重新安装运行 `./setup.ps1`（需要 uv）。本示例明确指定的配置从项目 `.env`、进程或 Windows 用户变量 `OPENROUTER_API_KEY` 读取密钥。模型/API 设置集中在配置目录的 **`configs/api.toml`**，两轮使用相同配置；不再通过 `OPENROUTER_MODEL` 设置模型。本示例所选模型是 **`openai/gpt-6-luna-decisions`**。

## 正式采集缓存与新判据重跑

可复用的采集资料统一放在 `data/channels/<平台>/<频道ID>/channel.json` 和同目录的 `covers/` 中，保存名称、简介、第一页标题/作品链接及本地封面；每个平台每个频道保存最新采集快照。正常采集和封面归档会自动更新正式缓存。`output/` 保存每轮实验的结果、请求、模型响应及本轮资料快照；封面直接引用正式缓存，不为每轮复制图片。查看或分享新报告时需保留对应的 `data/channels/`。旧实验文件不删除，避免已有 HTML 链接失效。

已有实验的采集资料可以导入正式缓存（只操作本地文件，不访问网站、不调用模型）：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.cache "output/douyin-all/20261012-192731-874954"
```

按新判据重跑完整抖音数据集，直接读正式缓存，不访问抖音或封面CDN，并创建新的时间目录：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --top-videos 5 --output "output/douyin-v7" --config configs/api.toml --category sign-language
```

缺失的频道缓存报错，不回退到网站；缺失的封面保留警告并仅使用该候选标题。新实验不复用旧判据的模型答案，两轮都重新调用。若实验中断，使用 `batch --resume "新实验的完整时间目录"` 继续，会自动保持离线、跳过已成功的新判断。普通 `--resume` 不会强制重跑成功项，更换判据应新建实验。

批量目前按频道顺序调用，每个有视频频道两轮请求。重新排除图文后请求数量会减少；完整两轮重跑此前粗估 **1.5–3小时**，第一轮标题数量、服务延迟或限流会影响时长。

### 重新采集并排除图文

旧缓存中的45863条作品没有保存类型字段，不能凭封面地址或程序拼出的 `/video/` 链接可靠地清除全部图文。若要重新访问全部频道，建议重新提取名称、简介和第一页作品，并复用已有视频封面。只访问每个主页的第一页，不主动翻页或滚动。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --refresh-cache --login-timeout 600 --output "output/cache-refresh"
```

这条命令只更新采集缓存，**不调用模型**，全部频道共用一个浏览器窗口。运行后记下终端显示的时间目录；中断后用 `batch --resume "output/cache-refresh/实际时间目录"` 继续，自动保持缓存更新模式，并跳过已完成的频道。不能用 `--refresh-cache` 覆盖或续跑旧分类实验。

图文识别优先使用 `aweme_type`（2/68/150）、图片列表及图片张数；页面回退检查实际 `/note/` 链接、图文标签和右上角叠放图片角标。文字文章也排除：实测类型为163，实际链接为 `/article/`，响应含 `article_info`。排除这些非视频作品后，实际作者卡片的 `/video/` 链接可作为视频证据；旧缓存根据ID拼出的链接不能作此证据。图文和文章也可能包含 `play_addr`，有播放地址不代表它是视频。作品类型仍无法确认时，缓存更新任务会报错并保留原正式缓存。续跑会先尝试用已保存的类型或DOM证据修复核实失败的频道；能修复的直接复用资料，不重访主页。

正式缓存的 `videos` 只保留核实的视频；排除的图文和文字文章资料保存在 `excluded_posts`，不进入标题排序、封面下载或模型输入。`first-page-posts.json` 保存第一页作品的类型、描述、封面地址、图片张数、时长和文章ID等证据，`post-type-status.json` 分别统计图片图文和文章，并记录未知作品ID。已有封面继续复用，旧非视频封面文件不主动删除。成功采集后覆盖 `data/channels/` 的最新频道资料，旧实验的CSV、模型响应和频道快照不改。

封面地址即使以 `.jpeg` 结尾也可能返回HEIC。项目使用 `pillow-heif` 解码，并统一保存为JPEG。频道资料更新成功不代表所有封面均下载成功；缺失原因见频道目录的 `archive-status.json`。离线实验若选中缺失封面的候选，只使用标题并保存警告，不访问网站补图。

更新完成后，使用上面的 `--from-cache` 命令做新实验，不再访问抖音。后续可以根据保存的类型证据离线调整过滤；只有旧缓存缺失这些字段时才需要重新访问网页。

## 模型/API 配置

显式通过 `--config configs/api.toml` 选择本示例的 API，通过 `--category sign-language` 选择类别。配置内有中文注释，密钥只填写到 `.env` 或环境变量中，配置文件仅保存对应的变量名称。

| 字段 | 用途 |
| --- | --- |
| `model` | 模型名称；换模型时需确认它支持图片及选定接口协议 |
| `api` | `decisions` 为结构化决策接口，`chat` 为聊天接口返回 JSON；它不是平台名称 |
| `endpoint` | 完整 HTTPS 请求地址；必须明确填写，本示例使用 OpenRouter 接口 |
| `api_key_env` | 读取密钥的环境变量名称，本示例为 `OPENROUTER_API_KEY` |
| `timeout_seconds` | 每次模型请求超时秒数，默认120；没有自动付费重试 |
| `context_budget` | 当前配置为1000000，未填写该字段时缺省60000；不是官方上下文上限，也不发给 API |
| `image_side` | 上传给模型的图片最长边，默认512像素；等比例缩小，保留本地原图 |
| `image_token_estimate` | 每张图片用于预算检查的固定估值，默认1536；不改变图片或实际计费 |

输入预算用文本的 UTF-8 字节数、固定图片估值和预留量估算，**不是精确 tokenizer 计数**。第一轮超预算时报错，不丢弃标题；第二轮超预算也会报错，不减少已选候选。2026-10-13查询 [OpenRouter 官方模型元数据](https://openrouter.ai/api/v1/models/openai/gpt-6-luna-decisions/endpoints)，该模型的 `context_length` 为 **1,050,000 tokens**；项目预算独立于该官方上限，当前配置已提高到1000000，换模型时需要重新评估。

两个图片设置可以保持默认，日常无需调整。`image_side` 会影响可见细节和传输量；若封面小字或手部细节不清晰，可提高到768/1024。`image_token_estimate` 仅参与本地估算，不是限制模型视觉处理能力的参数。

更换兼容服务时，修改 `api`、`model`、`endpoint`、`api_key_env`；目前只支持现有 Decisions 协议或 OpenAI 兼容 Chat Completions 协议，其他协议仍需代码适配。模型请求预览保存实际接口地址，换接口时不会复用旧接口的模型响应。

需要保留多套配置时复制 TOML 文件，并指定：

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音全部频道.csv --config configs/api-other.toml --output output/other-api --category sign-language
```

已移除 `--model`、`--api`、`--context-budget`、`--image-side`、`--image-token-estimate`；这些设置统一由配置文件读取。`--top-videos` 等实验参数仍保留。频道由模型独立判断，已移除分类命令的 `--threshold`。`--resume` 仍跳过成功结果，修改配置不会强制重跑已完成的频道。

## 检测流程

流程如下：

1. 在正常浏览器中访问作者主页，不滚动、不主动翻页。采集第一页作者作品的全部标题、视频地址、封面地址及频道名称/简介，此时不下载封面。优先取目标作者的第一页作品响应；响应未捕获时使用初始作者作品容器，并保存明确警告。
2. 第一轮只把全部视频标题输入决策模型，不发送账号名称、简介或平台资料，为每个视频返回手语概率，按概率降序排序；相同概率保留页面顺序。
3. 选择前 `--top-videos` 个候选（默认5），下载其封面；同时将第一页其余封面归档到本地供后续复用。第二轮模型只接收选中的候选，作品不足时使用实际数量。
4. 第二轮把账号名称、简介、候选标题和各自封面一起输入同一模型，按账号类型判断是否为手语频道，并独立判断各候选概率及最佳视频。

封面线索与 cover_audit v2 一致：主要视觉内容为真实人物正面（可以看不到脸，只见身体和手），或者封面有可辨读的“手语”文字，满足任意一项即可。此线索需结合标题判断自然手语，不能把手势舞当手语，也不能单凭封面或名称含“手语”就判频道为手语。本任务明确将手语舞按手语处理，两轮共用此规则。候选经过标题筛选，不代表全频道内容比例，媒体账号不能仅因选中的几个片段都含手语就被判正。英文 prompt 旁保留中文注释，版本为 `sign-language-v7-sign-language-dance-en`。

第一页和候选之外的历史作品未被检查，负预测不能排除历史视频中存在手语。概率是模型估计，尚未校准；只看静态封面无法确认连续手语动作。

## 批量输入与结果

CSV 必需列为 `主页网址`，可选列为 `平台`、`账户昵称`（或 `账户名称`）、`人工标注`（也兼容 `审核结果` 和旧列名 `真实标签`）。标签支持 `手语频道 / 疑难 / 不是手语频道` 和对应旧值 `1 / 0 / -1`；人工标注只用于输出对照，不输入模型。平台列支持快手、抖音，其他平台跳过。

也可直接输入多个链接，或使用 UTF-8 文本文件（每行一个链接，空行和 `#` 注释忽略）：

```powershell
.\.venv\Scripts\python.exe -m account_filter batch '第一个频道链接' '第二个频道链接' --top-videos 5 --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --urls-file channels.txt --top-videos 5 --config configs/api.toml --category sign-language
```

三种输入可混用。同一平台、同一作者去重；重复频道的人工标注冲突时报错。批量顺序执行，**整批只打开一个浏览器窗口，复用同一标签页切换频道**，两轮推理期间也保持窗口。普通错误记录后继续，风控立即停止；没有自动付费重试或 api-smoke。

每次创建 `--output/<北京时间到微秒>/`，不覆盖旧结果。主结果只有一个 `results.csv`，每个频道一行：

| 列 | 内容 |
| --- | --- |
| 账户名称、频道网址 | 实际采集名称和输入的主页链接 |
| 预测结果、人工标注 | 新预测仅“手语频道/不是手语频道”；人工“疑难”标注原样保留；失败或中断明确记录 |
| 预测与标注不符 | 有效预测和人工标注不一致时写 `预测与标注不符`；一致、未标注、未完成、失败或私密账号时留空 |
| 频道概率 | 第二轮独立返回的 `answers.channel_probability.noul`（0–1）；只供分析，失败、未完成或未调用模型时留空 |
| 最可能的视频 | 第二轮独立的 `best_video` 选择结果；选择 `none` 时为 `无候选`，可能与视频1不同 |
| 视频1分数、视频1链接、视频2分数、视频2链接…… | 每个视频拆成相邻两列，分数在前、链接在后；按第二轮分数降序排列，缺少的视频留空 |

CSV 使用 UTF-8 BOM，Excel 可直接打开，每完成一个频道就更新。默认有5组视频列，`--top-videos` 改变候选数量时按实际结果增加或减少列；历史快手结果的第6个视频也保留。

频道预测直接取自第二轮 `model-response.json` 的 `answers.channel.choice`（`yes` / `no`）：模型依据频道名称、简介、候选标题及封面，按个人/媒体等账号类型独立判断是否为手语频道，不输出疑难。频道概率另由 `answers.channel_probability.noul` 返回；不通过概率阈值、选择题概率分布或视频分数推导频道标签。终端按人工明确正负标注统计二类一致数，人工“疑难”不进入该统计。旧结果不自动改写，重跑请使用 `--from-cache` 创建新实验。

视频分数来自第二轮各视频问题的 `noul`，仅用于CSV排序。`最可能的视频` 则来自同一轮额外的 `best_video` 选择问题，依据标题和封面直接比较候选，并允许选择 `none`。当前最终抖音实验有3个频道的选择与最高分视频不同，因此保留这一列；具体频道信息仅在团队本地数据中保留，可以在原始响应里分别核对这两种判断。

## 离线可视化分析

抖音的图文/图集不作为视频候选：采集时保存 `aweme_type`、`content_type` 和 `image_count`，根据作品类型、图片列表或 `/note/` 链接排除图文；被排除的资料留在快照的 `excluded_posts` 中。第一页只有图文时记录 `no_video_posts`，本轮判为“不是手语频道”、概率留空，不调用模型；这只说明本轮第一页没有可用视频，不表示整个账号从未发布视频。旧快照没有这些字段且曾将所有链接拼成 `/video/`，不能仅凭旧链接或封面 URL 完整恢复类型，也不能将没有图文标记的截图作品认定为视频。


完整实验的交互报告保存在结果CSV同目录的 `analysis.html`，可以直接用浏览器打开。报告包括混淆矩阵、预测与标注不符/一致组的概率分布，以及频道明细筛选。全局筛选联动图表和明细；明细区可单独筛选不符、一致、误判方向、高置信不符和缺失概率等条目，按 CSV 原顺序展示。详情可查看已保存的简介、候选标题和本地封面。单条降级与疑难分流等规则模拟放在页面最后。

页面最后的“规则模拟复核”区默认模拟最新规则：保留原预测，原预测为“手语频道”且候选中恰好一个视频分数严格大于0.1时，改判为“不是手语频道”；原预测为“疑难”时，至少两个视频分数严格大于0.1则改判为“手语频道”，否则改判为“不是手语频道”。等于0.1不计数；原手语有0个或至少2个不改，原非手语不改。这里分流的是模型预测的疑难，不会改人工标注。展示准确率、手语精确率/召回率/F1的前后对比，并分别列出变对和变错的频道，支持搜索、分页及标题/封面详情。默认排除人工疑难，可勾选纳入对照；精确率、召回率和F1始终仅对人工明确正负类计算。下拉框保留此前“至少2条 ≥0.8”两种口径作为对照。只有明确未投稿的空候选按0条处理，其它完全缺失分数不参与对照。模拟只改变页面中的标签，不改变概率、原CSV或采集快照，上方原图表仍按原预测统计。本轮仍使用原候选，没有应用图文排查过滤。

点击“新规则下仍不符：全部条目”查看模拟后所有预测与人工标注不一致的频道，包含未改判但仍不符、改判后仍不符及新变错项。列表支持搜索、分页和候选标题/封面详情；勾选“包括人工疑难”可将这类标注也纳入。

修改CSV或完成下一轮实验后，重新生成：

```powershell
.\.venv\Scripts\python.exe -m account_filter.report "output/douyin-all/20261012-192731-874954/results.csv" --category sign-language
```

其它实验也可以传对应CSV。默认输出到CSV同目录；可用 `--output "报告路径.html"` 更改位置。报告生成和页面交互不访问抖音、不调用模型、不修改CSV，也不读取密钥或Cookie。图片只引用实验目录或 `data/channels/` 中的本地封面；分享时需一并保留所引用的正式缓存，旧报告的封面目录也需保留。缺失概率不补零，人工“疑难”从明确正负类的精确率分母中排除，三类一致率则包含它。

## 验证人物正面或“手语”文字封面的猜想

仅检查结果中**人工标注为手语频道**的原候选封面，不重新采集或访问抖音。每频道一次 OpenRouter 请求，最多5张缓存图片，模型直接返回“全部封面都符合”“至少一张符合”及逐张图片的判断。请求不包含名称、人工标签、标题和原手语分数。API沿用 `configs/api.toml`。英文判据及对应中文说明在 `account_filter/tasks/sign_language/cover_audit.py`；最新版 `front-cover-hypothesis-v2-person-or-sign-text` 使用或条件：主要视觉内容为真实人物正面（脸可不可见，只看到身体和手也可），或者封面本身有可辨读的“手语”文字。两项任意一项即可，不要求表情或特定手势。每次重新检查创建新时间目录，不复用不同判据的旧模型结果。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "output/douyin-all/20261012-192731-874954/results.csv" --config configs/api.toml
```

独立CSV保存在该实验的 `cover-audit/<北京时间>/cover-audit.csv`，一行一个频道，包含模型整组答案、概率及各候选的逐张判断。中间响应放共同的 `intermediate/` 中。原手语CSV和采集快照不改。结束后原 `analysis.html` 会加入“封面猜想验证”区，默认展示不符合；重建分析报告也会读取最近一次有效检查。缺图、模型无法判断和调用失败单独列出。

整组结论直接使用模型的 `all_front` 答案，不由程序逐张汇总替代。若整组与逐张答案冲突，CSV的“模型答案冲突”列会说明原因，HTML也可单独筛选；这些条目需要人工核对。旧版要求脸可见的检查覆盖484个手语标注频道、2387张可用封面（另1张缺失），模型整组判237个符合、247个不符合；至少一张符合的为452个，46个频道的整组与逐张答案冲突。这里只验证已筛出的最多5个候选，不证明全频道所有作品都具有该特征。

新版或条件实验位于 `cover-audit/20261013-171536-194577/`：同样484个频道、2387张可用封面，整组模型判305个符合、179个不符合；至少一张符合的为478个、不符合6个。94个频道的整组与逐张答案冲突。1次HTTP 503只重试了该失败频道，其余成功结果没有重复调用。独立CSV逐项与原始响应核对，原手语结果及旧版检查的校验值均保持不变，HTML默认展示新版不符项。

中断后继续同一检查目录，已有成功判断不再调用API；不要传 `--limit`，即可检查完整人工手语样本。支持 `--concurrency`（默认2）和 `--limit`（只检查前N个人工手语样本）。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "output/douyin-all/20261012-192731-874954/results.csv" --resume "output/douyin-all/20261012-192731-874954/cover-audit/20261013-171536-194577" --config configs/api.toml
```

## 停止后继续实验

`--resume` 指定已有的**时间目录**，直接更新其中的 `results.csv` 和原编号的 `intermediate/`，不会创建新时间目录。可以直接从结果CSV恢复频道列表和人工标注，也可传原输入CSV；传入时检查频道顺序及数量，避免写错行。

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --resume "output/douyin-all/20261012-192731-874954" --top-videos 5 --login-timeout 600 --config configs/api.toml --category sign-language
```

续跑跳过已完成的分类、已确认的私密账号和“用户不存在”，重试API错误、采集失败、中断及待处理项。完整 `channel.json` 优先复用，不重新访问这些作者主页；对应请求的证据与参数相同时复用已保存的模型响应，API失败后的成功标题排序也会保留。已保存的封面不重复下载，完整采集快照中的缺图自动补齐。旧的失败半成品不会当作完整快照。

删除结果CSV中的频道行后，续跑会按频道网址核对并复用原 `intermediate/` 目录；原目录编号保留，避免改动既有封面的路径。若同时使用 `--input-csv`，输入CSV也需要删除相应频道并保持剩余行顺序一致。

进度条的总数按频道计数，续跑起点包含已完成的频道；处理完一个失败/未完成频道后才增加。“缓存封面 x/y”是当前频道的视频进度，不是全数据集进度。完整缓存直接跳过，只有缺图时才显示补齐提示及对应频道编号；本轮处理完第一个频道后才估算剩余时间。

只补已采集频道的缓存、暂不继续实验：

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --resume "output/douyin-all/20261012-192731-874954" --backfill-only --headless
```

此模式只读取本地资料和保存的图片CDN地址，不访问作者主页、不调用模型、不采集尚未处理的频道。封面地址失效或缺失时写入 `archive-status.json`，不会为刷新图片地址自动重访作者。批量仍复用一个浏览器会话。中断下载后再续跑会保留已存图片。

抖音作品区明确显示“该账号还未发布过作品哦~”、没有视频、也没有登录或验证码提示时，识别为未投稿。没有公开作品可支持手语频道判断时记为 `不是手语频道`、`无候选`；不调用模型，频道概率留空，理由保存在 `classification-status.json`。单独的“暂无内容”不能用于该判断。私密账号记为 `无法判断（私密账号）`，不能据此判负，也不计入预测与标注的对照。

独立错误页明确显示“用户不存在”时，报 `UserNotFoundError`，结果列填写 `用户不存在`，频道概率、视频结果和预测与标注不符列留空；不按“不是手语频道”分类，不调用模型，之后续跑跳过该行。错误快照保存为 `collection_state: user_not_found`，保留页面文本、截图及明确原因。简介或视频标题引用这几个字不会触发该判断；登录弹窗和验证码优先处理。页面提示仅表示当次访问时无法获取账号，不能据此确定账号永久删除。

2026-10-12已离线核对本次全量实验的24张错误截图：19个未投稿、5个私密账号；已修正原CSV，并从保存截图恢复频道资料。没有重访作者或重新调用模型。5份旧截图中的简介已折叠，完整尾文无法离线恢复：保留 `bio_complete: false`、可确认的 `bio_visible_excerpt` 和原始截图，不补造缺失内容。

封面缺失情况以每个频道的 `archive-status.json` 为准；地址失效时保留缺失原因，不会为了刷新地址自动重访作者主页。旧的临时页面检查目录已清理。

## 中间文件

正式采集缓存位于 `data/channels/<平台>/<频道ID>/channel.json` 与 `covers/`。新实验的 `channel.json` 是本轮小型资料快照，封面路径指向正式缓存；旧实验原有的 `covers/` 保留，不删除或迁走。

命令行显示进度条、北京时间、已处理/总频道数、完成百分比、已用时间、预计剩余时间和当前阶段（采集、标题排序、下载封面、封面复判）。正常终端中每秒刷新同一行；重定向输出时按阶段变化写普通文本行。剩余时间按已处理频道的平均耗时估计，第一个频道完成前显示 `--:--:--`。扫码等待会显示在进度条中；错误原因和最终结果位置仍输出。

频道名称、简介、全部标题、候选和模型概率等详细中间信息只写文件，不在命令行逐条打印。批量中间文件统一放入本次时间目录下的 `intermediate/`，各频道仍按原编号区分：

```text
<输出父目录>/<时间>/
├── results.csv
└── intermediate/
    ├── 001_<频道id>/
    │   ├── channel.json
    │   ├── request-preview.json
    │   ├── model-response.json
    │   └── selected-videos.json
    └── 002_<频道id>/
```

已有批量目录也按此结构整理，并更新保存文件中的本地封面路径。单频道中间文件直接放在本次时间目录。

| 文件 | 内容 |
| --- | --- |
| `channel.json`、`channel-page.png`、`page-text.txt` | 名称/简介、全部标题、原始封面地址、本地封面路径、来源/范围和页面截图/文字；采集失败也保存已取得的部分资料 |
| `title-request-preview.json` | 第一轮全部标题、问题和输入预算 |
| `title-model-response.json` | 第一轮原始模型响应 |
| `title-ranking.json` | 全部标题按概率排序，以及选中的候选 ID |
| `selected-videos.json`、`covers/*.jpg` | 选中候选；封面目录归档第一页全部视频，模型只使用所选候选 |
| `archive-status.json` | 封面总数、本地数量、是否齐全和缺失原因；地址失效明确保留，不重新访问主页 |
| `classification-status.json` | 未投稿等规则判断的理由，明确记录没有调用模型 |
| `request-preview.json` | 第二轮标题/封面的对应关系、问题和预算，不含长 base64 |
| `model-response.json` | 第二轮原始响应及 usage |
| `collection-status.json`、`collection-error.png` | 采集状态；失败时的错误类型、原因和截图 |

采集第一页资料并保存全部封面，不调用模型：

```powershell
.\.venv\Scripts\python.exe -m account_filter collect '真实频道主页链接' --output output/check
```

重新分析保存资料，复用已有封面；选中视频缺图但有封面地址时下载该封面，不重新打开作者主页：

```powershell
.\.venv\Scripts\python.exe -m account_filter analyze '采集时间目录/channel.json' --top-videos 5 --output output/reanalyze --config configs/api.toml --category sign-language
```

`run / batch / analyze --dry-run` 只写采集资料和**第一轮标题输入预览**，不调用模型、不排序选候选、不下载封面，不能预览未知的第二轮选择。

## 登录和风控

Windows 检测到 Edge 时默认使用有窗口 Edge；可指定 `--browser-channel chrome`。浏览器数据保存在 `.browser/kuaishou/`，沿用原目录以保留已有快手会话，同一目录也保存抖音登录。不同平台 Cookie 按域隔离。

```powershell
.\.venv\Scripts\python.exe -m account_filter login '真实频道主页链接' --login-timeout 600
```

`login` 打开对应平台首页并等待扫码，登录后采集指定主页。`run / batch --login` 也支持同一窗口完成扫码。抖音主页出现登录弹窗时，有窗口采集自动等待扫码，默认 300 秒；不会在未登录时拿推荐链接冒充作者作品。会话保留在项目中，后续批次复用，无需每个频道扫码。任务结束后浏览器关闭；批次内不反复关闭再打开。

`--cookies 文件.json` 可导入 Playwright storage_state 或 Cookie 数组，仅接受快手/抖音域。密钥、Cookie 不进入模型请求；不要上传 `.env`、Cookie 文件或 `.browser/`。同一浏览器目录不能被两个任务同时打开。

快手作品区域仅显示“服务器异常，稍后重试”且无作品，或返回 `result:2`，报 `RiskControlError`。抖音出现验证码/访问频繁提示也停止。批量保留已完成结果，当前频道记录错误，其余标记 `未完成（对应平台风控）`。扫码与人机验证由本人完成，没有验证码识别或私有签名服务。

## 参数与实现

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `--top-videos` | 5 | 标题排序后复判的候选数，1–128；`--max-videos` 是兼容别名，含义同此项 |
| `--config` | 必须明确选择 | 读取模型、协议、接口地址、密钥变量名、超时和输入预算设置 |
| `--resume` | 不启用 | 在已有时间目录继续，保留成功结果并复用缓存 |
| `--backfill-only` | 不启用 | 配合 `--resume`，仅补已有频道的封面缓存 |

预算采用 UTF-8 字节长度加问题预留和图片估值，是保守启发式，不是精确 tokenizer。封面失败时明确记录警告，以标题继续；第二轮预览可检查实际图片数。

OpenRouter 请求使用 [`/api/alpha/decisions`](https://openrouter.ai/docs/guides/community/multimodal-decisions) 的 `state/questions` 格式，图片为顶层 base64 data URL。标题排序与封面复判是有依赖的步骤，分两次请求；同一轮的问题各自依据原始证据判断，符合 [OpenAI Decisions 指南](https://developers.openai.com/api/docs/guides/decisions)。没有证据表明本任务英文一定优于中文；可用相同模型和标注样本做中英对照。

共享采集编排位于 `account_filter/collector.py`，平台解析在 `account_filter/platforms/`，分类在 `classifier.py`，API 客户端在 `api.py`，CLI 编排在 `__main__.py`。没有引入数据库、Web 服务或插件框架。

## 样本与验证

`input/审核标签.csv` 已转换中文标签；原有 `input/快手测试22.csv` 为 10 个正例、2 个疑难、10 个负例。此前快手测试因风控停止，本次没有重启。

`input/抖音全部频道.csv` 保留审核表中的抖音记录及原有五列顺序。按此前要求删除私密和用户不存在等指定账号后，当前为2140条：手语频道484条、疑难4条、不是手语频道1652条。全量实验命令见 [运行指南](commands.zh-CN.md)。

`input/抖音测试3.csv` 从同一审核表选取3个频道，原标签依次为正例、疑难、负例；具体身份不随项目公开。2026-10-12 登录后，复用一个窗口完成两轮真实调用，每个频道复判 5 张封面；预测标签与原标签一致。前两个频道使用初始作者作品 DOM，分别采集 36/39 条，第三个采集 5 条。少量样本仅验证链路，不代表总体准确率。

此前简介选择器未命中抖音主页的实际简介块，导致有简介的频道被保存为空。现已补上作者资料内的简介选择器和结构回退，保留简介换行；自动点击简介中的“更多”，支持页面展开及与简介开头匹配的浮层，去除“更多/收起”控件文字，并优先保留完整文本。不能获取时明确提示可能为空或解析失败，不再断言公开资料没有简介。临时简介检查输出已清理，最新采集资料统一保存在 `data/channels/`。历史模型结果保留原样，不把后采集的资料写回旧请求。

`input/抖音实验25.csv` 最初按随机种子 42 从审核标签中抽取 10 个手语频道、全部 5 个疑难、10 个不是手语频道，不重复、不补造标签。类别交错执行。实验使用当前 `classifier.py` 中用户简化后的 prompt，默认每个频道选择前 5 个候选复判。人工标注只用于事后对照。按后续要求，已从项目CSV中删除指定的私密账号；样本保留原文件名，当前为 **10+4+10，共24条**。

最终汇总位于 `output/douyin-experiment/20261012-170305-348124/results.csv`，当前保留24个成功判断，与原审核标签一致为 **18/24（75.0%）**。原实验另有1个私密账号失败，其行现已删除。完整采集/复判的6个长简介更新到新时间目录，其余结果复用；各时间目录的推理响应保留，CSV已统一调整列结构。来源与复判目录记在 `experiment-settings.json`。此次仅编辑代码、文件布局和已有CSV，没有重新运行实验。这一结果不能单独证明简介修复或 prompt 简化带来的因果变化。

| 人工标注 | 预测手语频道 | 预测疑难 | 预测不是手语频道 | 失败 |
| --- | ---: | ---: | ---: | ---: |
| 手语频道（10） | 8 | 0 | 2 | 0 |
| 疑难（4） | 2 | 2 | 0 | 0 |
| 不是手语频道（10） | 2 | 0 | 8 | 0 |

6 个不一致样本分别为：2个疑难→手语、2个不是手语→手语、2个手语→不是手语；具体身份仅保留在团队本地数据中。优先检查对应的 `title-ranking.json`、候选封面与 `request-preview.json`。判负只覆盖当前第一页候选，不能排除历史作品有手语。

24 个成功项共复判 118 个候选，所有候选均有本地封面；其中一个频道只有 3 个作品，所以使用 3 个候选。20 个频道捕获第一页作品响应，4 个使用初始作者作品 DOM并明确记录来源。23 个频道采集到非空简介；另一个频道的保存页面没有显示简介，保留空值和警告。最终汇总中已没有待处理项或已知折叠简介。

本地测试不访问平台、不调用付费 API：

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.cache/pytest-check
```

覆盖标题全集、排序和封面复判顺序、候选数量、同一浏览器会话复用、跨平台输入、作者过滤、第一页游标、风控停止、CSV 列排序及输出目录防覆盖。
