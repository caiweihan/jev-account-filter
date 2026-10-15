[English](commands.md) | [简体中文](commands.zh-CN.md)

# 运行指南

在项目根目录的 PowerShell 执行。分类必须明确选择 `--config` 和 `--category`，程序不预设服务商或目标类别。

## 新分类实验

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --top-videos 5 --output output/my-experiment
.\.venv\Scripts\python.exe -X utf8 -m account_filter run "真实频道主页链接" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml"
```

配置文件需先准备，见 [配置说明](configuration.zh-CN.md)。`--platform auto` 按链接识别，可混合抖音和快手，也可指定 `douyin` 或 `kuaishou`。平台识别与分类类别无关。

输入 CSV 必需 `主页网址`；可选 `平台`、`账户昵称`、`人工标注`，兼容 `审核结果` 与 `真实标签`。正负标签由类别配置定义，也接受 `1/0/-1`。人工标注只用于事后对照。

公开格式样例见 [`input/channels.example.csv`](../input/channels.example.csv)。其中所有账号均为虚构，运行前请替换主页链接；团队真实输入文件不随仓库公开。

## 只读缓存的新实验

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --from-cache --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --output output/new-experiment
```

不访问平台或封面 CDN，仍调用明确选定的模型。新实验不复用旧模型答案。

## 一个具体示例：手语任务

这条命令明确选择已有服务配置和手语规则，不代表项目默认值：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --config configs/api.toml --category sign-language --top-videos 5 --output output/sign-language-next
```

## 续跑

新实验保存 `category.json`、`api-config.json`。有这些快照时无需再次输入选择：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/实验/时间目录"
```

读取的是这次实验已经明确选定的配置，而非系统默认。缺少快照的旧实验需显式提供：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/douyin-v7/20261014-113151-009297" --config configs/api.toml --category sign-language --top-videos 5
```

跳过成功项，重试失败与未完成项，更新同一个 CSV。更换目标类别须创建新实验。

## 只采集 / 更新缓存

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter collect "真实频道主页链接"
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --refresh-cache --login-timeout 600 --output output/cache-refresh
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/cache-refresh/实际时间目录"
```

只采集时不需要模型或类别配置，不调用 API。新浏览器会话在 `.browser/profile/`；复用旧会话时显式加 `--browser-dir .browser/kuaishou`。

## 可视化

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/实验/时间目录/results.csv"
```

分类标签从本实验的 `category.json` 读取。如果旧实验无快照，需要 `--category`，例如：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/douyin-v7/20261014-113151-009297/results.csv" --category sign-language
```

生成同目录 HTML，不修改 CSV，不访问平台或模型。仅当类别配置明确启用报告扩展时，才附加其专用分析区。

## 可选的手语封面审核工具

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "结果CSV路径" --config configs/api.toml
```

这是单独的任务工具，会调用明确选定的模型；不属于通用分类入口的默认流程。
