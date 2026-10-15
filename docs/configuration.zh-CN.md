[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# 配置说明

`configs/` 保存可选配置。分类必须明确指定 API 和类别；程序不自动载入其中任意一份。密钥只从所选配置指明的环境变量读取。

## API 服务身份必须完整

以下四项必填，缺失或留空立即报错：

```toml
api = "chat"
model = "YOUR_VISION_MODEL"
endpoint = "https://your-provider.example/v1/chat/completions"
api_key_env = "MODEL_API_KEY"
```

`api` 是协议：`chat` 对应 OpenAI 兼容 Chat Completions，`decisions` 对应已支持的结构化决策协议。服务商由完整 `endpoint` 决定，换协议不会自动选择服务地址。模型应支持图片与本项目的 JSON 输出参数；其他原生协议仍需适配。

远程用 HTTPS；本机回环地址可用 HTTP。密钥写到项目 `.env`、进程或 Windows 用户环境变量中；无鉴权本地服务可使用非敏感占位值。

`configs/api-chat.example.toml` 是服务商无关的模板，使用前替换占位值。`configs/api.toml` 是此前实验的一份具体 OpenRouter 配置，只在明确通过 `--config` 选择时使用。

与服务商、类别无关的运行参数仍有普通默认值，可按需要覆盖：

| 字段 | 未填写时的值 | 用途 |
| --- | ---: | --- |
| `timeout_seconds` | 120 | 请求超时，不自动重试付费调用 |
| `context_budget` | 60000 | 本地字节数与图片估值预算，不是官方上下文上限 |
| `image_side` | 512 | 上传图片最长边，原图不变 |
| `image_token_estimate` | 1536 | 每图预算估值，不是实际计费 |

## 类别必须明确选择

`--category` 接受 `configs/categories/` 下的名称或完整 TOML 路径。分类规则、正负标签、问题文本和版本均来自该文件。

- `id/name/version`：身份、名称和版本。
- `positive_label/negative_label`：正负标签。
- `title_rules/title_video_instructions`：只看标题的第一轮。
- `rules/channel_*`：资料、标题与封面的账户判据和独立概率。
- `video_*`、候选相关字段：逐视频问题和最佳候选，使用 `{key}` 对应作品。
- `analysis_warning`：该任务的证据范围说明。
- `report_extension`：可选任务报告模块；不填只生成通用报告。

`sign-language` 和 `fitness.example.toml` 都是可选示例。手语的专用封面检查、规则模拟与报告组件在 `account_filter/tasks/sign_language/`，不在通用代码中推定。

新实验保存类别和非敏感 API 配置快照。续跑只能读取已有明确选择；旧实验无快照时必须显式指定。历史结果、采集缓存和已有报告不自动改写。

## 平台与类别独立

平台域名和路径在 `configs/platforms.toml`，解析在 `account_filter/platforms/`。目前实现抖音、快手。按链接自动识别平台只是路由，不会选择目标类别或模型服务。

微信、YouTube、TikTok 尚未实现；仅添加 TOML 条目不能获得采集能力。所有现有类别均使用“第一页视频标题 → 候选封面”证据流程，需要正文或视频帧的任务仍需扩展采集流程。
