[English](installation.md) | [简体中文](installation.zh-CN.md)

# Installation and environment

To inspect existing results, open [`analysis.html`](../analysis.html) in Edge or Chrome and select a CSV and optional data folders. No Python environment is required. The steps below are for collection, model experiments, or rebuilding the viewer.

Run commands from the project root. Python 3.11 or later is required; the current local environment uses 3.12. You can continue using the existing `.venv`; the project reorganization did not add runtime dependencies.

Installation is documented directly, without a platform-specific setup script. Dependencies and browser downloads stay inside the project.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --cache-dir .cache/pip -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/.cache/ms-playwright"
.\.venv\Scripts\python.exe -m playwright install chromium
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --cache-dir .cache/pip -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.cache/ms-playwright" .venv/bin/python -m playwright install chromium
```

Linux also needs Playwright's system libraries. Collection defaults to the installed Edge on Windows when available and to downloaded Chromium otherwise. For other commands in these docs, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` on macOS/Linux; activation is not required.

## Credentials and configuration

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; Path('.env').write_bytes(Path('configs/env.example').read_bytes())"
```

On macOS/Linux, use `.venv/bin/python` for the same copy command.

In `.env`, set the variable named by `api_key_env` in your chosen API configuration. The variable name is entirely configuration-driven; `MODEL_API_KEY` is a generic example, and the program does not default to any provider's credential variable. You can also use environment variables. Keep keys out of TOML files.

See [Configuration](configuration.md) for model and endpoint settings.

## Login

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter login "真实频道主页链接" --login-timeout 600
```

Scan the QR code in the browser. New sessions are saved to the platform-neutral `.browser/profile/` directory, with one browser window per batch. To reuse an earlier session, explicitly add `--browser-dir .browser/kuaishou`; the old directory has not been deleted or moved. Two tasks cannot use the same session directory simultaneously.


## Next steps

Run `collect --input-csv input/accounts.csv --output data/my-dataset`, then `screen --data data/my-dataset --config configs/api.toml --category sign-language --output results/my-experiment`. These are independent collection and screening steps. See [Commands](commands.md) for complete invocations and [Data format](data-format.md) to use your own sources.

No installation is needed to inspect the demonstration: open the root `analysis.html` to analyze six real public examples.
