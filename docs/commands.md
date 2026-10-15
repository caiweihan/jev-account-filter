[English](commands.md) | [简体中文](commands.zh-CN.md)

# Commands

Run these commands in PowerShell from the project root. Classification requires explicit `--config` and `--category` selections; the program does not assume a provider or target category.

## New classification experiment

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --top-videos 5 --output output/my-experiment
.\.venv\Scripts\python.exe -X utf8 -m account_filter run "真实频道主页链接" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml"
```

Prepare the configuration files first; see [Configuration](configuration.md). `--platform auto` identifies the platform from each URL and supports mixed Douyin and Kuaishou inputs. You can also specify `douyin` or `kuaishou`. Platform detection is independent of the classification category.

Input CSVs require `主页网址` (profile URL). Optional columns are `平台` (platform), `账户昵称` (account nickname), and `人工标注` (human annotation); `审核结果` and `真实标签` are also accepted for labels. Positive and negative labels are defined by the category configuration; `1/0/-1` values are accepted too. Human annotations are used only for comparison after inference.

See [`input/channels.example.csv`](../input/channels.example.csv) for a public format example. All accounts are fictional; replace its profile URLs before running. The team's real input files are not distributed with the repository.

## New experiment using only cached evidence

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --from-cache --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --output output/new-experiment
```

This does not visit the platform or thumbnail CDN, but still calls the explicitly selected model. New experiments do not reuse previous model answers.

## A concrete example: sign-language screening

This command explicitly selects an existing service configuration and sign-language rules. These are not project defaults:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --config configs/api.toml --category sign-language --top-videos 5 --output output/sign-language-next
```

## Resume

New experiments save `category.json` and `api-config.json`. When these snapshots exist, you do not need to repeat the selections:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/实验/时间目录"
```

The command reads the configuration explicitly selected for that experiment, rather than a system default. For older experiments without snapshots, supply the configuration explicitly:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/douyin-v7/20261014-113151-009297" --config configs/api.toml --category sign-language --top-videos 5
```

Successful entries are skipped, failed and incomplete entries are retried, and the same CSV is updated. Create a new experiment when changing the target category.

## Collection only / cache refresh

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter collect "真实频道主页链接"
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --refresh-cache --login-timeout 600 --output output/cache-refresh
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/cache-refresh/实际时间目录"
```

Collection-only runs need neither model nor category configuration and do not call the API. New browser sessions use `.browser/profile/`; explicitly add `--browser-dir .browser/kuaishou` to reuse an old session.

## Visualization

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/实验/时间目录/results.csv"
```

Classification labels are read from that experiment's `category.json`. If an older experiment has no snapshot, provide `--category`, for example:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/douyin-v7/20261014-113151-009297/results.csv" --category sign-language
```

An HTML file is generated in the same directory without modifying the CSV or accessing the platform or model. Task-specific analysis sections are included only when the category configuration explicitly enables a report extension.

## Optional sign-language thumbnail audit

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "结果CSV路径" --config configs/api.toml
```

This standalone task tool calls the explicitly selected model. It is not part of the generic classification entry point's default workflow.
