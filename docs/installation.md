[English](installation.md) | [简体中文](installation.zh-CN.md)

# Installation and environment

Run commands from the project root. Python 3.11 or later is required; the current local environment uses 3.12. You can continue using the existing `.venv`; the project reorganization did not add runtime dependencies.

For a new environment, install [uv](https://docs.astral.sh/uv/getting-started/installation/) first, then run:

```powershell
.\setup.ps1
```

The script creates `.venv/` inside the project, installs `requirements.txt`, and downloads Playwright Chromium. When Edge is available on Windows, collection uses the installed Edge browser by default.

## Credentials and configuration

```powershell
Copy-Item configs/env.example .env
```

In `.env`, set the variable named by `api_key_env` in your chosen API configuration. The variable name is entirely configuration-driven; `MODEL_API_KEY` is a generic example, and the program does not default to any provider's credential variable. You can also use environment variables. Keep keys out of TOML files.

See [Configuration](configuration.md) for model and endpoint settings.

## Login

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter login "真实频道主页链接" --login-timeout 600
```

Scan the QR code in the browser. New sessions are saved to the platform-neutral `.browser/profile/` directory, with one browser window per batch. To reuse an earlier session, explicitly add `--browser-dir .browser/kuaishou`; the old directory has not been deleted or moved. Two tasks cannot use the same session directory simultaneously.

Do not commit `.env`, cookies, browser sessions, or experiment caches to a public repository. See [Commands](commands.md) for everyday usage.

## Public sample and private data

[`input/channels.example.csv`](../input/channels.example.csv) contains three entirely fictional accounts and demonstrates the supported CSV columns. Its IDs, names, URLs, and labels are invented, not sampled from the team's dataset. Replace the example URLs before running; `1` and `-1` map to the selected category's positive and negative labels, and a blank annotation is allowed. [`configs/channels.example.txt`](../configs/channels.example.txt) provides fictional URL-list examples too.

The publication boundary is defined in `.gitignore`: real input CSVs, `output/`, the canonical `data/` cache, `.cache/`, `.browser/`, `.venv/`, credentials, and cookies stay local. The synthetic sample CSV is explicitly allowed. Channel names, biographies, titles, thumbnails, and model requests/responses can identify the team's collected accounts even when stored outside `input/` and `output/`.

Git ignore rules apply to Git file selection, not to manually zipping the entire project directory. Share source files and the synthetic examples, rather than an archive of the full local workspace. Summary experiment statistics in the public documentation do not include individual account identities.
