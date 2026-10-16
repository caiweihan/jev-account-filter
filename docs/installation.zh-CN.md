[English](installation.md) | [简体中文](installation.zh-CN.md)

# 安装与环境

如果只查看已有结果，可直接在 Edge 或 Chrome 中打开根目录的 [`analysis.html`](../analysis.html)，选择 CSV 和可选采集数据文件夹；无需安装 Python 环境。以下步骤用于运行采集、模型实验或重新打包查看器。

在项目根目录执行命令。Python 需 3.11 及以上，当前本地为 3.12。现有 `.venv` 可继续使用，本次整理没有新增运行依赖。

安装步骤直接列在文档中，不需要平台专用安装脚本。依赖和浏览器均保存在项目内。

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

Linux 还需满足 Playwright 的系统库要求。Windows 有 Edge 时采集默认使用本机 Edge；其它系统使用已安装的 Chromium。运行文档中的命令时，将 `.\.venv\Scripts\python.exe` 换成 `.venv/bin/python` 即可，无需激活环境。

## 密钥与配置

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; Path('.env').write_bytes(Path('configs/env.example').read_bytes())"
```

macOS/Linux 将复制命令中的 Python 路径换为 `.venv/bin/python`。

在 `.env` 填写 API 配置中 `api_key_env` 对应变量。变量名称完全由所选 API 配置指定；`MODEL_API_KEY` 是通用示例，程序不默认读取某个服务商的密钥。也可以使用环境变量，密钥不要放在 TOML 中。

设置模型与接口见 [配置说明](configuration.zh-CN.md)。

## 登录

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter login "真实频道主页链接" --login-timeout 600
```

在浏览器中扫码。新会话默认保存到平台中性的 `.browser/profile/`，批次内只用一个窗口。需要复用以前的会话时显式加 `--browser-dir .browser/kuaishou`，旧目录没有删除或搬动。同一会话目录不能由两个任务同时打开。


## 下一步

先运行 `collect --input-csv input/accounts.csv --output data/my-dataset`，再运行 `screen --data data/my-dataset --config configs/api.toml --category sign-language --output results/my-experiment`。两步分别采集和筛选，不隐式访问另一阶段。完整命令见 [运行指南](commands.zh-CN.md)；已有自己的数据时见 [数据格式](data-format.zh-CN.md)。

仅查看演示无需安装依赖：直接打开根目录 `analysis.html`，即可查看 6 个真实公开样例。
