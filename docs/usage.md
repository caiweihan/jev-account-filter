[English](usage.md) | [简体中文](usage.zh-CN.md)

# Sign-language experiment guide and historical records

This document preserves the detailed procedures and records of the original sign-language task. The configurations below explicitly select a sign-language experiment; they are not defaults of the generic program. The project is now organized as Jev Account Filter, with commands consistently using `account_filter`. See [Installation](installation.md), [Commands](commands.md), and [Configuration](configuration.md) for setup, current commands, and optional configurations.

Kuaishou and Douyin profile URLs are supported. The target is a **sign-language channel**: one or two credible signing videos may suffice for a personal account, while accounts whose names and biographies indicate unrelated local media, entertainment news, or similar topics face stricter criteria. An occasional signing video alone does not make such a media account positive. Media accounts explicitly focused on sign language or sign-language accessibility can still be positive. **In this task, sign-language dance (手语舞) counts as sign language; gesture dance (手势舞) does not.** The project remains a small Python CLI tool, with its environment, browser sessions, and caches kept inside the project.

## Running

```powershell
cd path\to\jev-account-filter
.\.venv\Scripts\python.exe -m account_filter run 'https://www.kuaishou.com/profile/EXAMPLE_KUAISHOU_ACCOUNT_B' --top-videos 5 --output output/my-channel --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音测试3.csv --top-videos 5 --output output/douyin-test --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音实验25.csv --top-videos 5 --output output/douyin-experiment --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音全部频道.csv --top-videos 5 --login-timeout 600 --output output/douyin-all --config configs/api.toml --category sign-language
```

Dependencies live in `.venv/`; run `./setup.ps1` to reinstall them (requires uv). The explicitly selected configuration in this example reads `OPENROUTER_API_KEY` from the project's `.env`, process environment, or Windows user environment. Model/API settings are centralized in **`configs/api.toml`**, and both passes use the same configuration. `OPENROUTER_MODEL` is no longer used to select the model. The model explicitly selected by this example is **`openai/gpt-6-luna-decisions`**.

## Canonical collection cache and reruns with new criteria

Reusable collected evidence is stored in `data/channels/<platform>/<channel-ID>/channel.json` and its sibling `covers/` directory: names, biographies, first-page titles/work URLs, and local thumbnails. Each platform/channel keeps its latest collection snapshot. Normal collection and thumbnail archiving update the canonical cache automatically. `output/` stores experiment results, requests, model responses, and experiment-specific metadata snapshots. Thumbnails reference the canonical cache directly instead of being copied into every experiment. Keep the corresponding `data/channels/` files when viewing or sharing new reports. Old experiment files are retained so existing HTML links continue to work.

Collected evidence from an existing experiment can be imported into the canonical cache using only local files, without visiting websites or calling a model:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.cache "output/douyin-all/20261012-192731-874954"
```

To rerun the complete Douyin dataset with new criteria, read the canonical cache directly without visiting Douyin or its thumbnail CDN, creating a new timestamped directory:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --top-videos 5 --output "output/douyin-v7" --config configs/api.toml --category sign-language
```

A missing channel cache raises an error rather than falling back to the website. Missing thumbnails produce warnings, with only the corresponding candidate title used. New experiments do not reuse model answers from previous criteria; both passes call the model again. If interrupted, resume with `batch --resume "<full timestamped directory of the new experiment>"`. This preserves offline mode and skips successful new judgments. Ordinary `--resume` does not force successful entries to rerun; create a new experiment when changing criteria.

Batches currently call accounts sequentially, using two requests for each account with videos. Excluding image posts reduces the number of requests. A previous rough estimate for a complete two-pass rerun was **1.5–3 hours**, depending on title counts, service latency, and rate limits.

### Recollecting evidence and excluding image posts

The 45,863 works in the old cache lacked type fields. Thumbnail URLs or program-generated `/video/` links cannot reliably identify all image posts. When revisiting every account, recollect the name, biography, and first-page works while reusing existing video thumbnails. Only the first profile page is visited; the program does not deliberately paginate or scroll.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --refresh-cache --login-timeout 600 --output "output/cache-refresh"
```

This command updates collection caches only and **does not call the model**. All accounts share one browser window. Record the timestamped directory printed by the terminal. After interruption, use `batch --resume "output/cache-refresh/<actual timestamped directory>"`; it preserves cache-refresh mode and skips completed accounts. `--refresh-cache` cannot overwrite or resume an old classification experiment.

Image-post detection prioritizes `aweme_type` values 2/68/150, image lists, and image counts. DOM fallback checks actual `/note/` links, image-post labels, and stacked-image badges at the upper right. Text articles are excluded too: the observed type is 163, actual links use `/article/`, and responses contain `article_info`. After excluding these non-video works, an actual `/video/` link on the creator's own card can serve as video evidence; a link constructed from an old cached ID cannot. Image posts and articles may also contain `play_addr`, so a playback address does not prove that a work is a video. If the post type remains uncertain, cache refresh raises an error and preserves the previous canonical cache. Resuming first tries to repair failed type verification using saved type or DOM evidence; repairable accounts reuse existing evidence without revisiting the profile.

The canonical cache's `videos` contains only verified videos. Excluded image posts and text articles are retained in `excluded_posts` and do not enter title ranking, thumbnail downloads, or model input. `first-page-posts.json` preserves first-page evidence such as type, description, thumbnail URL, image count, duration, and article ID. `post-type-status.json` separately counts image posts and articles and records unknown post IDs. Existing thumbnails are reused; old non-video thumbnail files are not actively deleted. Successful collection replaces the latest channel metadata under `data/channels/`, while old experiment CSVs, model responses, and channel snapshots remain unchanged.

A thumbnail URL ending in `.jpeg` may still return HEIC. The project decodes it using `pillow-heif` and saves JPEG. A successful metadata refresh does not imply that every thumbnail was downloaded; missing-image reasons are recorded in the channel's `archive-status.json`. If an offline experiment selects a candidate whose thumbnail is missing, it uses the title alone and records a warning rather than visiting the website to fetch it.

After refreshing, use the `--from-cache` command above for a new experiment without visiting Douyin. Saved type evidence also allows future offline filtering changes. Revisiting pages is needed only when the old cache lacks that evidence.

## Model/API configuration

Explicitly select this example's API with `--config configs/api.toml` and its category with `--category sign-language`. The configuration has Chinese comments. Put keys only in `.env` or environment variables; the configuration file stores the corresponding variable name.

| Setting | Purpose |
| --- | --- |
| `model` | Model name; a replacement must support images and the selected API protocol |
| `api` | `decisions` selects structured decisions; `chat` selects a chat interface returning JSON. This is not a platform name |
| `endpoint` | Complete HTTPS request URL, explicitly required; this example uses OpenRouter |
| `api_key_env` | Credential environment-variable name; `OPENROUTER_API_KEY` in this example |
| `timeout_seconds` | Timeout per model request in seconds, default 120; no automatic paid retries |
| `context_budget` | 1000000 in the current configuration; 60000 when omitted. Not an official context-window limit and not sent to the API |
| `image_side` | Longest image edge sent to the model, default 512 pixels; downscaled proportionally while preserving the local original |
| `image_token_estimate` | Fixed per-image estimate for budget checks, default 1536; changes neither images nor actual billing |

The input budget combines UTF-8 text bytes, a fixed per-image estimate, and reserved overhead; **it is not an exact tokenizer count**. An over-budget first pass raises an error without dropping titles. An over-budget second pass also raises an error without reducing the selected candidates. [Official OpenRouter model metadata](https://openrouter.ai/api/v1/models/openai/gpt-6-luna-decisions/endpoints), checked on October 13, 2026, reported a `context_length` of **1,050,000 tokens**. The project's budget is independent of that official limit; its current configuration raises the budget to 1000000, which must be reassessed when changing models.

Both image settings can normally stay at their defaults. `image_side` affects visible detail and transfer size; increase it to 768/1024 if small thumbnail text or hand details are unclear. `image_token_estimate` is only part of the local estimate, not a parameter limiting the model's visual processing ability.

To change compatible services, update `api`, `model`, `endpoint`, and `api_key_env`. Only the existing Decisions protocol and OpenAI-compatible Chat Completions are currently supported; other protocols require code changes. Request previews store the actual endpoint. Switching endpoints does not reuse responses from the old service.

To retain several configurations, copy the TOML file and select it explicitly:

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --input-csv input/抖音全部频道.csv --config configs/api-other.toml --output output/other-api --category sign-language
```

`--model`, `--api`, `--context-budget`, `--image-side`, and `--image-token-estimate` have been removed; their settings now come from the configuration file. Experiment parameters such as `--top-videos` remain. The model judges the channel independently, and classification commands no longer expose `--threshold`. `--resume` still skips successful results; changing configuration does not force completed accounts to rerun.

## Detection pipeline

The pipeline is:

1. Visit the creator's profile in a normal browser without scrolling or deliberate pagination. Collect all first-page titles, video URLs, thumbnail URLs, and the channel name/biography, without downloading thumbnails yet. Prefer the target creator's first-page post response; if it was not captured, use the initial creator-post container and save an explicit warning.
2. Send only all video titles to the decision model in the first pass, without the account name, biography, or platform metadata. Obtain a sign-language probability per video and sort in descending order, preserving page order for ties.
3. Select the first `--top-videos` candidates (default 5) and download their thumbnails. Archive the remaining first-page thumbnails locally for later reuse. The second pass receives only selected candidates; if fewer exist, use the available count.
4. Send the account name, biography, candidate titles, and their corresponding thumbnails to the same model in the second pass. Judge whether it is a sign-language channel according to account type, and independently estimate candidate probabilities and select the best video.

Thumbnail cues match cover_audit v2: either a real person facing the camera as the main visual subject (the face may be invisible, with only the body and hands shown), or legible “手语” (sign language) text on the thumbnail. Either condition suffices as a cue. Combine it with the title to assess natural signing; do not mistake gesture dance for sign language or classify a channel solely because its name or thumbnail contains “手语”. This task explicitly counts sign-language dance as signing, and both passes share that rule. Candidates are title-selected and do not represent the proportion of content across the entire channel. A media account cannot be positive solely because its few selected clips contain signing. English prompts retain corresponding Chinese comments; the version is `sign-language-v7-sign-language-dance-en`.

Historical works beyond the first page and selected candidates are not inspected. A negative prediction cannot rule out signing in older videos. Probabilities are uncalibrated model estimates, and static thumbnails cannot confirm continuous signing motion.

## Batch inputs and results

The required CSV column is `主页网址` (profile URL). Optional columns are `平台` (platform), `账户昵称` or `账户名称` (account name), and `人工标注` (human annotation), also accepting `审核结果` and the legacy `真实标签`. Labels support `手语频道 / 疑难 / 不是手语频道` (sign-language channel / uncertain / not a sign-language channel) and their legacy values `1 / 0 / -1`. Human annotations are only compared after inference and are not sent to the model. The platform column supports Kuaishou and Douyin; other platforms are skipped.

You can also supply multiple URLs directly or a UTF-8 text file with one URL per line; blank lines and `#` comments are ignored:

```powershell
.\.venv\Scripts\python.exe -m account_filter batch '第一个频道链接' '第二个频道链接' --top-videos 5 --config configs/api.toml --category sign-language
.\.venv\Scripts\python.exe -m account_filter batch --urls-file channels.txt --top-videos 5 --config configs/api.toml --category sign-language
```

All three input methods can be combined. Entries are deduplicated by platform and creator; conflicting human annotations for a duplicate channel cause an error. Batches execute sequentially. **The entire batch opens one browser window and reuses the same tab to navigate between accounts**, keeping the window open during both inference passes. Ordinary errors are recorded before continuing; risk-control detection stops the batch immediately. There are no automatic paid retries or api-smoke calls.

Each run creates `--output/<Beijing timestamp to microseconds>/`, preserving old results. There is one main result file, `results.csv`, with one row per channel:

| Column | Content |
| --- | --- |
| `账户名称`, `频道网址` | Collected account name and input profile URL |
| `预测结果`, `人工标注` | New predictions are only `手语频道/不是手语频道`; human `疑难` labels are retained, and failures/interruptions are explicit |
| `预测与标注不符` | Contains `预测与标注不符` when a valid prediction differs from the human annotation; blank for matches, unlabeled/incomplete/failed entries, or private accounts |
| `频道概率` | Independently returned second-pass `answers.channel_probability.noul` (0–1), for analysis only; blank for failed/incomplete entries or when no model was called |
| `最可能的视频` | The second pass's independent `best_video` choice; `无候选` when it chooses `none`, potentially different from video 1 |
| `视频1分数`, `视频1链接`, `视频2分数`, `视频2链接`, … | Adjacent score/URL columns per video, score first; sorted by descending second-pass score, with unavailable videos left blank |

The CSV uses UTF-8 with BOM for opening directly in Excel and is updated after each channel. There are five video-column pairs by default; `--top-videos` increases or decreases them according to actual results. The sixth video from historical Kuaishou results is preserved too.

The channel prediction comes directly from second-pass `model-response.json` at `answers.channel.choice` (`yes` / `no`). Based on the name, biography, candidate titles, and thumbnails, the model independently judges whether it is a sign-language channel, applying account-type criteria such as personal versus media accounts, without returning uncertain. The channel probability is a separate `answers.channel_probability.noul` answer. Labels are not derived from a probability threshold, a choice-question probability distribution, or video scores. The terminal counts binary agreement only for explicit positive/negative human annotations, excluding human `疑难` entries. Old results are not rewritten automatically; create a new `--from-cache` experiment to rerun.

Video scores are the second pass's per-video `noul` answers and are used only for CSV ordering. `最可能的视频` comes from an additional `best_video` choice in the same pass, directly comparing titles and thumbnails with `none` as an allowed answer. In the finalized Douyin experiment, three channels chose a different video from the highest-scored one, so the column is retained. Their identities remain in the team's local data; both judgments can be checked separately in the raw response.

## Offline visualization

Douyin image posts/galleries are not video candidates. Collection saves `aweme_type`, `content_type`, and `image_count`, excluding image posts through type evidence, image lists, or `/note/` links. Excluded metadata stays in `excluded_posts`. If the first page contains only image posts, it records `no_video_posts`, predicts `不是手语频道` for this run with no probability, and does not call the model. This means only that the current first page has no usable video, not that the account has never posted videos. Old snapshots lacked these fields and generated `/video/` URLs for every work; old links or thumbnail URLs cannot completely recover post types, nor does a screenshot without an image-post marker prove that a work is a video.

The interactive report for a complete experiment is saved as `analysis.html` beside the result CSV and opens directly in a browser. It includes a confusion matrix, probability distributions for matching and mismatching groups, and channel-detail filters. Global filters update charts and details together. The detail section independently filters disagreements, agreements, error directions, high-confidence mismatches, missing probabilities, and similar cases, displaying entries in original CSV order. Details show the saved biography, candidate titles, and local thumbnails. Rule simulations such as single-video downgrading and uncertain-case routing appear at the end of the page.

The final “规则模拟复核” (rule-simulation review) section defaults to the latest simulated rule: preserve the original prediction, but downgrade a predicted sign-language channel to negative when exactly one candidate score is strictly greater than 0.1. For an original `疑难` prediction, classify it as positive if at least two scores are strictly greater than 0.1, otherwise negative. A score equal to 0.1 does not count. Original positives with zero or at least two qualifying videos remain unchanged, as do original negatives. This routes uncertain **model predictions**, without changing human annotations. The section compares accuracy and sign-language precision/recall/F1 before and after the rule, listing newly correct and newly incorrect channels separately with search, pagination, and title/thumbnail details. Human uncertain labels are excluded by default but can be included for comparison; precision, recall, and F1 always use explicit binary human labels only. The selector retains the two earlier “at least 2 videos ≥0.8” variants for comparison. Empty candidates count as zero only for confirmed accounts with no posts; otherwise completely missing scores are excluded. Simulation changes only page-level labels, leaving probabilities, original CSVs, and snapshots unchanged. The charts above continue to use original predictions. This simulation uses the original candidates without applying image-post filtering.

Click “新规则下仍不符：全部条目” (all remaining disagreements under the new rule) to inspect every channel whose simulated prediction differs from its human annotation. This includes unchanged disagreements, changed predictions that still disagree, and newly incorrect cases. Search, pagination, and candidate title/thumbnail details are available. “包括人工疑难” includes uncertain human annotations too.

After modifying the CSV or finishing another experiment, regenerate the report:

```powershell
.\.venv\Scripts\python.exe -m account_filter.report "output/douyin-all/20261012-192731-874954/results.csv" --category sign-language
```

You can pass other experiments' CSVs as well. Output defaults to the CSV's directory; `--output "<report path.html>"` overrides it. Neither report generation nor page interaction visits Douyin, calls the model, changes the CSV, or reads keys/cookies. Images reference only the experiment directory or `data/channels/`; keep the referenced canonical cache when sharing, as well as thumbnail directories used by old reports. Missing probabilities are not replaced with zero. Human `疑难` entries are excluded from precision calculated over explicit binary labels, but included in three-class agreement.

## Testing the front-facing person or sign-language-text thumbnail hypothesis

Only the original candidate thumbnails of channels **human-annotated as sign-language channels** are audited, without recollection or visits to Douyin. One OpenRouter request per channel sends up to five cached images. The model directly returns whether all thumbnails qualify, whether at least one qualifies, and per-image judgments. Requests exclude the account name, human label, video titles, and original signing scores. The API uses `configs/api.toml`. English criteria and corresponding Chinese explanations are in `account_filter/tasks/sign_language/cover_audit.py`. The latest version, `front-cover-hypothesis-v2-person-or-sign-text`, uses an OR condition: a real front-facing person as the main subject (the face may be invisible, with only the body and hands visible), or legible “手语” text on the thumbnail itself. Either suffices; expressive faces or particular hand poses are not required. Each new audit creates a timestamped directory and does not reuse model results from different criteria.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "output/douyin-all/20261012-192731-874954/results.csv" --config configs/api.toml
```

A separate CSV is saved at `cover-audit/<Beijing timestamp>/cover-audit.csv` under the experiment directory. Each row represents one channel, including group-level model answers, probabilities, and per-candidate image judgments. Intermediate responses share an `intermediate/` directory. The original sign-language CSV and collection snapshots remain unchanged. On completion, the original `analysis.html` gains a “封面猜想验证” (thumbnail hypothesis audit) section, displaying nonconforming cases by default. Regenerating the report also reads the latest valid audit. Missing images, unjudgeable cases, and failed calls are listed separately.

The group-level conclusion uses the model's `all_front` answer directly rather than programmatically aggregating per-image judgments. If group and image answers conflict, the CSV's `模型答案冲突` column explains why, and HTML supports filtering those cases for human review. The earlier face-visible criterion covered 484 human-positive channels and 2,387 available thumbnails, with one additional missing image. The model's group answer accepted 237 channels and rejected 247; 452 channels had at least one qualifying thumbnail, and 46 had conflicts between group and per-image answers. This tests only the up-to-five selected candidates and does not establish the feature for all works on a channel.

The revised OR-condition experiment is under `cover-audit/20261013-171536-194577/`. For the same 484 channels and 2,387 available images, group-level answers accepted 305 and rejected 179; 478 channels had at least one qualifying image and six had none. Ninety-four channels had group/per-image conflicts. A single HTTP 503 was retried only for the failed channel; successful channels were not called again. The separate CSV was checked against raw responses, and checksums of the original sign-language results and previous audit remained unchanged. HTML displays the revised nonconforming cases by default.

After interruption, resume the same audit directory; successful judgments do not call the API again. Omit `--limit` to cover every human-positive account. `--concurrency` defaults to 2; `--limit` audits only the first N human-positive accounts.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "output/douyin-all/20261012-192731-874954/results.csv" --resume "output/douyin-all/20261012-192731-874954/cover-audit/20261013-171536-194577" --config configs/api.toml
```

## Resuming an interrupted experiment

`--resume` selects an existing **timestamped directory** and directly updates its `results.csv` and original numbered `intermediate/` directories without creating a new timestamp. Channel URLs and human annotations can be restored from the results CSV alone. The original input CSV may also be supplied; its channel order and count are checked to prevent updating the wrong rows.

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --resume "output/douyin-all/20261012-192731-874954" --top-videos 5 --login-timeout 600 --config configs/api.toml --category sign-language
```

Resuming skips completed classifications, confirmed private accounts, and nonexistent users, retrying API errors, collection failures, interrupted entries, and pending work. Complete `channel.json` snapshots are preferred, avoiding profile revisits. Saved model responses are reused when request evidence and parameters match; successful title ranking survives a later API failure too. Existing thumbnails are not downloaded again, and missing images in complete collection snapshots are backfilled automatically. Old partial failures are not treated as complete snapshots.

After channel rows are deleted from the results CSV, resuming matches by channel URL and reuses the original `intermediate/` directory. Original directory numbers remain to preserve thumbnail paths. If `--input-csv` is also supplied, delete the same channels there and retain the order of the remaining rows.

The progress bar counts channels, with its initial resumed count including completed ones. It advances only after processing a failed/incomplete channel. “缓存封面 x/y” (caching thumbnails) is progress within the current channel, not the entire dataset. Complete caches are skipped; backfill messages and the channel index appear only for missing images. Remaining-time estimates begin after the first channel processed in the current run completes.

To backfill caches for already collected channels without continuing classification:

```powershell
.\.venv\Scripts\python.exe -m account_filter batch --resume "output/douyin-all/20261012-192731-874954" --backfill-only --headless
```

This mode reads only local evidence and saved image-CDN URLs. It does not visit creator profiles, call a model, or collect unprocessed accounts. Expired or missing thumbnail URLs are recorded in `archive-status.json`; the program does not automatically revisit a creator to refresh image URLs. The batch still shares one browser session, and downloaded images are preserved after interruption.

A Douyin account is recognized as having no posts when its works section explicitly shows “该账号还未发布过作品哦~” (this account has not published any works), has no videos, and displays no login or CAPTCHA prompt. With no public works supporting a sign-language-channel judgment, it records `不是手语频道` and `无候选` without a model call; the account probability stays blank and `classification-status.json` records the reason. “暂无内容” (no content) alone is insufficient. Private accounts are recorded as `无法判断（私密账号）` (cannot determine: private account), not classified as negative, and excluded from prediction/annotation comparison.

An independent error page explicitly showing “用户不存在” (user does not exist) raises `UserNotFoundError`. The result is `用户不存在`, with account probability, video results, and the mismatch column blank. It is not classified as negative, does not call a model, and is skipped on later resumes. Error snapshots preserve `collection_state: user_not_found`, page text, screenshot, and the explicit reason. Mentions of the same words in biographies or video titles do not trigger this state; login dialogs and CAPTCHAs take priority. The page only indicates that the account was unavailable during that visit and does not establish permanent deletion.

On October 12, 2026, the 24 error screenshots from the full experiment were reviewed offline: 19 accounts had no posts and five were private. The original CSV was corrected, and channel metadata was recovered from saved screenshots without revisiting profiles or calling the model. Biographies were collapsed in five old screenshots, so their complete endings could not be recovered offline. Those entries preserve `bio_complete: false`, the verifiable `bio_visible_excerpt`, and the original screenshot, without inventing missing content.

Each channel's `archive-status.json` is authoritative for missing thumbnails. Expired URLs retain an explanation without automatic profile revisits to refresh them. Old temporary page-inspection directories have been cleaned up.

## Intermediate files

The canonical collection cache is at `data/channels/<platform>/<channel-ID>/channel.json` and `covers/`. A new experiment's `channel.json` is a small metadata snapshot whose thumbnail paths point to the canonical cache. Existing `covers/` directories in old experiments are retained, not deleted or relocated.

The terminal shows a progress bar, Beijing time, processed/total channels, percentage, elapsed time, estimated remaining time, and current phase (collection, title ranking, thumbnail download, or thumbnail reassessment). An interactive terminal refreshes the same line every second; redirected output writes plain lines when the phase changes. Remaining time uses average processing time per completed channel and shows `--:--:--` until the first completes. QR-login waiting appears in the progress bar; errors and final result paths are still printed.

Detailed intermediate data—names, biographies, all titles, candidates, and model probabilities—are written only to files, not printed entry by entry. Batch intermediate files share `intermediate/` under the current timestamped directory, keeping each channel's original index:

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

Existing batch directories have been organized this way, with saved local thumbnail paths updated accordingly. Single-channel intermediate files live directly under the current timestamped directory.

| File | Content |
| --- | --- |
| `channel.json`, `channel-page.png`, `page-text.txt` | Name/biography, all titles, original thumbnail URLs, local thumbnail paths, provenance/scope, and page screenshot/text; partial evidence is also saved after collection failure |
| `title-request-preview.json` | First-pass titles, questions, and input budget |
| `title-model-response.json` | Raw first-pass response |
| `title-ranking.json` | All titles ranked by probability, plus selected candidate IDs |
| `selected-videos.json`, `covers/*.jpg` | Selected candidates; the thumbnail directory archives all first-page videos, while only selected candidates enter the model |
| `archive-status.json` | Total/local thumbnail counts, completeness, and missing-image reasons; expired URLs are explicit without revisiting profiles |
| `classification-status.json` | Reasons for rule-based outcomes such as no posts, explicitly recording that no model was called |
| `request-preview.json` | Second-pass title/thumbnail alignment, questions, and budget, without long base64 payloads |
| `model-response.json` | Raw second-pass response and usage |
| `collection-status.json`, `collection-error.png` | Collection state; error type, reason, and screenshot after failure |

Collect first-page metadata and save all thumbnails without calling the model:

```powershell
.\.venv\Scripts\python.exe -m account_filter collect '真实频道主页链接' --output output/check
```

Reanalyze saved evidence and reuse existing thumbnails. If a selected video's thumbnail is missing but its URL exists, download it without reopening the creator's profile:

```powershell
.\.venv\Scripts\python.exe -m account_filter analyze '采集时间目录/channel.json' --top-videos 5 --output output/reanalyze --config configs/api.toml --category sign-language
```

`run / batch / analyze --dry-run` saves collected evidence and the **first-pass title-input preview** only. It does not call the model, rank/select candidates, or download thumbnails, and cannot preview unknown second-pass selections.

## Login and risk controls

On Windows, collection uses visible Edge by default when detected; `--browser-channel chrome` selects Chrome. Browser data is stored in `.browser/kuaishou/`, retaining the original directory to preserve earlier Kuaishou sessions; the same directory also stores Douyin login. Cookies are isolated by platform domain.

```powershell
.\.venv\Scripts\python.exe -m account_filter login '真实频道主页链接' --login-timeout 600
```

`login` opens the platform's homepage and waits for QR login, then collects the requested profile. `run / batch --login` also supports QR login in the same window. When a Douyin profile displays a login dialog, visible collection automatically waits for scanning, for 300 seconds by default. It does not substitute recommendation links for creator works while logged out. Sessions stay in the project for reuse in later batches, without scanning for every channel. The browser closes when the task finishes but is not repeatedly closed and reopened during a batch.

`--cookies <file.json>` imports Playwright storage_state or a cookie array, accepting only Kuaishou/Douyin domains. Keys and cookies are excluded from model requests. Do not upload `.env`, cookie files, or `.browser/`. Two tasks cannot open the same browser directory simultaneously.

Kuaishou raises `RiskControlError` when its works area shows only “服务器异常，稍后重试” (server error, try again later) with no works, or returns `result:2`. Douyin CAPTCHA/frequent-access warnings also stop the task. Batches preserve completed results, record the current channel's error, and mark the rest `未完成（对应平台风控）` (incomplete: platform risk control). Users complete QR login and human verification themselves; no CAPTCHA-recognition or private-signature service is used.

## Parameters and implementation

| Parameter | Default | Purpose |
| --- | --- | --- |
| `--top-videos` | 5 | Number of candidates reassessed after title ranking, 1–128; `--max-videos` is a compatible alias with the same meaning |
| `--config` | Explicit selection required | Model, protocol, endpoint, credential-variable name, timeout, and input-budget settings |
| `--resume` | Disabled | Continue an existing timestamped directory, preserving successful results and reusing cached evidence |
| `--backfill-only` | Disabled | With `--resume`, only backfill thumbnail caches of existing channels |

The budget uses UTF-8 byte length plus question overhead and image estimates: a conservative heuristic, not exact tokenizer counting. Thumbnail failures produce explicit warnings and processing continues with the title; second-pass previews show the actual image count.

OpenRouter requests use the [`/api/alpha/decisions`](https://openrouter.ai/docs/guides/community/multimodal-decisions) `state/questions` format, with images as top-level base64 data URLs. Title ranking and thumbnail reassessment are dependent steps and use separate requests. Questions within a pass judge the original evidence independently, consistent with the [OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions). There is no evidence that English necessarily outperforms Chinese for this task; compare languages using the same model and labeled examples.

Shared collection orchestration is in `account_filter/collector.py`, platform parsing in `account_filter/platforms/`, classification in `classifier.py`, the API client in `api.py`, and CLI orchestration in `__main__.py`. No database, web service, or plugin framework was introduced.

## Samples and validation

`input/审核标签.csv` has been converted to Chinese text labels. The original `input/快手测试22.csv` contains ten positives, two uncertain cases, and ten negatives. The earlier Kuaishou test was stopped after risk controls and was not restarted in this update.

`input/抖音全部频道.csv` retains the review table's Douyin records and original five-column order. After removing the specified private/nonexistent accounts as previously requested, it contains 2,140 entries: 484 sign-language channels, four uncertain cases, and 1,652 negatives. See [Commands](commands.md) for the full experiment command.

`input/抖音测试3.csv` selects three channels from the same review table, originally labeled positive, uncertain, and negative, respectively; their identities are not distributed with the project. After login on October 12, 2026, one shared window completed two real model calls per channel, reassessing five thumbnails each. Predictions matched the original labels. The first two used initial creator-post DOMs and yielded 36/39 works; the third yielded five. This small sample validates the pipeline, not overall accuracy.

The earlier biography selector missed the actual Douyin biography block, saving empty biographies for accounts that had one. Creator-profile selectors and structural fallbacks have been added, preserving line breaks. The collector automatically clicks “更多” (more), handles inline expansion and overlays matching the beginning of the biography, removes “更多/收起” (more/collapse) controls, and prefers complete text. Failure now explicitly means the biography may be empty or parsing failed, rather than asserting no public biography exists. Temporary biography-inspection outputs have been cleaned up, and the latest evidence is consolidated under `data/channels/`. Historical model results stay unchanged; later-collected evidence is not written back into old requests.

`input/抖音实验25.csv` originally sampled ten sign-language channels, all five uncertain cases, and ten negatives from the review labels with random seed 42, without duplicates or invented annotations, interleaved by category. The experiment used the user's simplified prompt then present in `classifier.py`, selecting the top five candidates per channel by default. Human annotations were only used for later comparison. The specified private account was subsequently removed from project CSVs; the original filename remains, with **10+4+10 = 24 entries** now.

The final summary is at `output/douyin-experiment/20261012-170305-348124/results.csv`, retaining 24 successful judgments with **18/24 (75.0%)** agreement with the original review labels. One private account originally failed; its row has been removed. Full collection/reassessment for six long biographies was saved to a new timestamped directory, with other results reused. Inference responses remain in their respective directories, and CSV columns have been standardized. Provenance and reassessment directories are recorded in `experiment-settings.json`. That update edited code, file organization, and existing CSVs without rerunning the experiment. The result alone cannot establish a causal effect of biography fixes or prompt simplification.

| Human annotation | Predicted signing channel | Predicted uncertain | Predicted negative | Failed |
| --- | ---: | ---: | ---: | ---: |
| Sign-language channel (10) | 8 | 0 | 2 | 0 |
| Uncertain (4) | 2 | 2 | 0 | 0 |
| Not a sign-language channel (10) | 2 | 0 | 8 | 0 |

The six disagreements were two uncertain → positive cases, two negative → positive cases, and two positive → negative cases. Their identities remain only in the team's local data. First inspect their `title-ranking.json`, candidate thumbnails, and `request-preview.json`. A negative judgment covers only the current first-page candidates and does not rule out signing in older works.

The 24 successful entries reassessed 118 candidates, all with local thumbnails. One channel had only three works and therefore three candidates. Twenty channels had captured first-page work responses; four used the initial creator-post DOM with explicit provenance. Twenty-three had nonempty biographies. Another channel's saved page showed no biography, so the empty field and warning were retained. The final summary had no pending entries or known collapsed biographies.

Local tests do not visit platforms or call paid APIs:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp=.cache/pytest-check
```

Coverage includes complete title sets, ranking/reassessment order, candidate counts, shared browser sessions, cross-platform inputs, creator filtering, first-page cursors, risk-control stopping, CSV column ordering, and protection against output-directory overwrites.
