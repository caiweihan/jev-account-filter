[English](commands.md) | [简体中文](commands.zh-CN.md)

# Commands

Collection and screening are independent: first collect a dataset, then screen it. Screening never opens platform pages or downloads thumbnails.

## 1. Collect account data

The input CSV requires `主页网址` (profile URL). Optional columns are `账户昵称` (nickname) and `人工标注` (annotation; `审核结果` is also accepted).

```powershell
.\.venv\Scripts\python.exe -m account_filter login "PROFILE_URL"
.\.venv\Scripts\python.exe -m account_filter collect --input-csv input/accounts.csv --output data/my-dataset
```

One or more profile URLs may also be supplied directly:

```powershell
.\.venv\Scripts\python.exe -m account_filter collect "PROFILE_URL_1" "PROFILE_URL_2" --output data/my-dataset
```

The dataset contains names, biographies, first-page video titles, URLs, and local thumbnails. A collection run shares one browser window, without scrolling or pagination. Image posts and articles are excluded from video candidates. Risk-control errors stop collection while preserving completed data.

```powershell
.\.venv\Scripts\python.exe -m account_filter collect --resume data/my-dataset
```

Resuming skips completed accounts and retries failed or unfinished entries. Missing-image reasons are recorded in each account's `archive-status.json`; missing thumbnails do not trigger another profile visit. Login sessions stay in `.browser/profile/`; concurrent tasks must not share one session directory.

## 2. Screen the collected dataset

```powershell
.\.venv\Scripts\python.exe -m account_filter screen --data data/my-dataset --config configs/api.toml --category sign-language --top-videos 5 --output results/my-experiment
```

Both `--config` and `--category` are explicit; no provider or category is chosen by default. Pass one sees only titles. Pass two receives the account name, biography, and selected titles/thumbnails. The model judges the account category independently. `--top-videos` defaults to 5; `--dry-run` saves only the first-pass request preview.

```powershell
.\.venv\Scripts\python.exe -m account_filter screen --resume results/my-experiment
```

Resuming restores the dataset location, API settings, and category rules; successful results are skipped and failures are retried. Use a new experiment name when changing models, rules, or candidate counts.

Results go directly to `results/my-experiment/results.csv`. Requests, responses, and title rankings live in `intermediate/`. No timestamp directory is added. Nonempty destinations are rejected to prevent overwrites. Screening does not modify collected evidence.

## Custom sources

No platform collector is required. Prepare a dataset following the [data format](data-format.md), validate it, and use the same `screen` command:

```powershell
.\.venv\Scripts\python.exe -m account_filter validate-data data/custom-dataset
```

## Inspect results

Open the root `analysis.html` in Edge/Chrome. On first use it automatically displays six real public examples. Select your own results CSV and collected-data directories to replace them. An optional second-review CSV is incorporated into the same performance and error analysis. Files remain local, and the browser remembers the last analysis.

The examples are deliberately selected demonstrations, not an accuracy benchmark. See the [publication scope](../examples/real-demo/README.md).

On macOS/Linux use `.venv/bin/python` instead. See [Installation](installation.md) and [Configuration](configuration.md).
