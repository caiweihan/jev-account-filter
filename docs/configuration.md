[English](configuration.md) | [简体中文](configuration.zh-CN.md)

# Configuration

`configs/` contains optional configurations. Classification requires explicit API and category selections; the program does not load any of these files automatically. Keys are read only from the environment variable named in the selected configuration.

## API service settings

```toml
api = "chat"
model = "YOUR_VISION_MODEL"
endpoint = "https://your-provider.example/v1/chat/completions"
api_key_env = "MODEL_API_KEY"
```

`api` selects the protocol: `chat` uses OpenAI-compatible Chat Completions, while `decisions` uses the supported structured-decision protocol. The complete `endpoint` determines the provider; changing the protocol does not select a service URL automatically. The model must support images and the project's JSON-output parameters.

Use HTTPS for remote services; HTTP is allowed for local loopback addresses. Store keys in the project's `.env`, process environment, or Windows user environment variables.

`configs/api-chat.example.toml` is a provider-neutral template; replace its placeholders before use. `configs/api.toml` is a specific OpenRouter configuration from earlier experiments, used only when explicitly selected with `--config`.

Provider- and category-independent operational settings still have ordinary defaults, which you can override:

| Setting | Value when omitted | Purpose |
| --- | ---: | --- |
| `timeout_seconds` | 120 | Request timeout; paid calls are not retried automatically |
| `context_budget` | 60000 | Local byte-based text and image estimate budget, not an official context-window limit |
| `image_side` | 512 | Longest edge of an uploaded image; the original stays unchanged |
| `image_token_estimate` | 1536 | Per-image budget estimate, not actual billing |

## Select a category explicitly

`--category` accepts a name under `configs/categories/` or a full TOML path. Classification rules, positive/negative labels, question text, and version all come from that file.

- `id/name/version`: identity, display name, and version.
- `positive_label/negative_label`: positive and negative labels.
- `title_rules/title_video_instructions`: the title-only first pass.
- `rules/channel_*`: account criteria and independent probability based on metadata, titles, and thumbnails.
- `video_*` and candidate-related fields: per-video questions and the best candidate, using `{key}` to identify each work.
- `analysis_warning`: the evidence-scope explanation for the task.
- `report_extension`: an optional task report module; omitting it produces only the generic report.

`sign-language` and `fitness.example.toml` are optional examples. Sign-language-specific thumbnail audits, rule simulations, and report components live in `account_filter/tasks/sign_language/`; generic code does not infer them.

New experiments save category and non-sensitive API configuration snapshots. Resuming uses an existing explicit selection; older experiments without snapshots require explicit arguments. Historical results, collected data, and existing reports are not rewritten automatically.

## Platforms and categories are independent

Platform domains and URL paths are configured in `configs/platforms.toml`; parsers live in `account_filter/collection/platforms/`. Douyin and Kuaishou are currently implemented. URL-based platform detection is routing only: it does not select a target category or model service.

WeChat, YouTube, and TikTok are not implemented yet; adding a TOML entry alone does not provide collection support. All existing categories use the “first-page video titles → candidate thumbnails” evidence pipeline. Tasks requiring full post text or video frames also need collection extensions.
