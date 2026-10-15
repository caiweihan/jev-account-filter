[English](installation.md) | [简体中文](installation.zh-CN.md)

# 安装与环境

如果只查看已有结果，可直接在 Edge 或 Chrome 中打开根目录的 [`analysis.html`](../analysis.html)，选择 CSV 和可选缓存文件夹；无需安装 Python 环境。以下步骤用于运行采集、模型实验或重新打包查看器。

在项目根目录执行命令。Python 需 3.11 及以上，当前本地为 3.12。现有 `.venv` 可继续使用，本次整理没有新增运行依赖。

新环境先安装 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后运行：

```powershell
.\setup.ps1
```

脚本在项目内创建 `.venv/`、安装 `requirements.txt` 并下载 Playwright Chromium。Windows 有 Edge 时实际采集默认使用本机 Edge。

## 密钥与配置

```powershell
Copy-Item configs/env.example .env
```

在 `.env` 填写 API 配置中 `api_key_env` 对应变量。变量名称完全由所选 API 配置指定；`MODEL_API_KEY` 是通用示例，程序不默认读取某个服务商的密钥。也可以使用环境变量，密钥不要放在 TOML 中。

设置模型与接口见 [配置说明](configuration.zh-CN.md)。

## 登录

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter login "真实频道主页链接" --login-timeout 600
```

在浏览器中扫码。新会话默认保存到平台中性的 `.browser/profile/`，批次内只用一个窗口。需要复用以前的会话时显式加 `--browser-dir .browser/kuaishou`，旧目录没有删除或搬动。同一会话目录不能由两个任务同时打开。

`.env`、Cookie、浏览器会话与实验缓存不需要提交到公共仓库。日常命令见 [运行指南](commands.zh-CN.md)。

## 公开样例与私有数据

[`input/channels.example.csv`](../input/channels.example.csv) 包含3个完全虚构的账号，展示支持的CSV字段。账号ID、名称、链接和标签均为编造，不是从团队数据中抽取；运行前请替换示例链接。`1`、`-1` 分别映射为所选类别的正负标签，人工标注也可以留空。[`configs/channels.example.txt`](../configs/channels.example.txt) 同样提供虚构的链接列表样例。

`.gitignore` 定义了公开范围：真实输入CSV、`output/`、正式 `data/` 缓存、`.cache/`、`.browser/`、`.venv/`、密钥和Cookie保留在本地，仅明确放行虚构样例CSV。频道名称、简介、标题、封面和模型请求/响应即使位于 `input/`、`output/` 之外，也可能暴露团队收集的账号。

Git忽略规则只影响Git选取文件，不会过滤手动压缩整个项目目录的内容。发布时应分享源码和虚构样例，不打包完整本地工作区。公开文档保留的实验汇总统计不包含具体账号身份。
