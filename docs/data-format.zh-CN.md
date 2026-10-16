[English](data-format.md) | [简体中文](data-format.zh-CN.md)

# 数据集格式（版本 1）

数据集是采集与筛选之间的正式接口。自定义来源按此格式准备即可，无需修改爬虫、登记平台或实现网络接口。模型仍只读取元信息、标题和静态封面。

```text
my-dataset/
├── dataset.json
├── manifest.csv
└── channels/
    └── example/
        ├── channel.json
        └── covers/1.jpg
```

`dataset.json`:

```json
{"schema_version": 1, "manifest": "manifest.csv"}
```

`manifest.csv` (UTF-8):

```csv
platform,account_id,url,name,annotation,path,status,error
custom,example,https://example.org/account,Example,,channels/example/channel.json,ready,
```

`channel.json`:

```json
{
  "platform": "custom",
  "id": "example",
  "url": "https://example.org/account",
  "name": "Example",
  "bio": "Account biography",
  "scope": "All videos on the collected first page",
  "videos": [
    {
      "id": "1",
      "title": "Video title",
      "url": "https://example.org/video/1",
      "content_type": "video",
      "cover_path": "covers/1.jpg"
    }
  ]
}
```

## 字段约定

- `manifest.csv` 中每个账户一行，所有表头均必需。`platform + account_id` 唯一，且与 JSON 的 `platform + id` 一致；URL 也必须一致。自定义来源可以使用任意非空平台名，例如 `custom`。
- `path` 相对于数据集根目录，`cover_path` 相对于该账户 JSON 所在目录。都必须是目录内的相对路径，不允许越界或远程图片。可移动整个数据集而不改变链接。
- `annotation` 是可选人工标签值，可以留空；它仅用于结果对照，不发送给模型。其余列保留空值而不是删列表头。
- `status`：`ready` 为可筛选；`private`、`user_not_found` 是明确不可用状态；`pending`、`failed` 表示采集未完成，筛选会记录对应错误。
- 账户 JSON 的 `platform/id/url/name/bio/videos` 必需，文本字段为字符串；`videos` 为数组，每个视频必须有唯一、非空的 `id`，以及字符串 `title/url`。标题、简介可以为空。
- `videos` 只放已核实的视频；图文、文章不能放入其中，可另存 `excluded_posts`。无作品账户用空数组并附 `no_posts: true`；只有非视频作品时附 `no_video_posts: true`。空候选按当前规则判负且不调用模型。
- `cover_path` 可省略；缺图时模型只看该标题，记录缺失而不自动下载。封面建议 JPEG/PNG/WebP；仅静态图片，不需要完整视频。
- `scope` 建议写明采集时间、第一页范围或人工选择的子集，避免将少数候选误当整个频道。额外的来源和作品类型证据可保留，筛选器不推断平台私有字段。

```powershell
.\.venv\Scripts\python.exe -m account_filter validate-data data/my-dataset
```

`screen` 读取后不修改数据集。结果、规则快照和模型响应保存在独立的 `results/<实验名>/`。真实可运行的格式示例见 [`examples/real-demo/data`](../examples/real-demo/data)。

## 内置采集与扩展

内置抖音与快手采集器直接输出这个格式。平台实现位于 `account_filter/collection/platforms/`，筛选与 API 位于 `account_filter/screening/`。新增采集平台时添加同名适配模块并在 `configs/platforms.toml` 登记；自定义数据来源只需生成数据文件，不受内置平台列表限制。

## 可选封面核验数据

封面核验独立于分类结果。分析页面会在所选实验目录读取 `cover-audit/latest.json`，例如 `{"path":"cover-audit/text-check/audit-results.json"}`。`path` 相对于实验目录；数据中的 `source_sha256` 必须与原结果 CSV 的 SHA-256 一致，否则不显示。

展示元数据由核验文件提供：`title` 是标题，`criteria` 是判据说明，`population` 是核验对象范围；都作为纯文本显示，不执行 HTML。模型、版本、时间分别用 `model/prompt_version/generated`。这些字段可描述任何领域的封面标准。

`rows` 每项以原 CSV 的 `id`（从 1 开始）和 `url` 对齐，包含 `name/manual/prediction/status/videos`。`overall` 是所有候选符合标准的整组答案，`any_front` 是至少一张符合的答案；每项使用 `choice`（`yes/no/unclear`）、显示文本 `label` 和三项 `probabilities`。逐候选答案放在 `videos[].front`。保留整组与逐张的独立判断，不用程序汇总替代模型结论。`csv`、`response` 和 `cover` 使用实验目录内或正式采集目录中的本地文件链接；浏览器仅解析主动选择的文件。
