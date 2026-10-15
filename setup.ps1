$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.cache/uv'
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PSScriptRoot '.cache/ms-playwright'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '请先安装 uv: https://docs.astral.sh/uv/getting-started/installation/' }
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    uv venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建环境失败' }
}
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败' }
.venv/Scripts/python.exe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw '浏览器安装失败' }
