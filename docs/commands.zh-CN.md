[English](commands.md) | [简体中文](commands.zh-CN.md)

# 运行指南

流程分为两部分：先采集数据，再使用数据筛选。两部分独立运行；筛选阶段不会打开平台主页或下载图片。

## 1. 从账户列表采集数据

输入 CSV 需要“主页网址”列，可有“账户昵称”和“人工标注”（也接受“审核结果”）。

```powershell
.\.venv\Scripts\python.exe -m account_filter login "账户主页链接"
.\.venv\Scripts\python.exe -m account_filter collect --input-csv input/accounts.csv --output data/my-dataset
```

也可直接传入一个或多个主页链接：

```powershell
.\.venv\Scripts\python.exe -m account_filter collect "账户主页链接1" "账户主页链接2" --output data/my-dataset
```

数据包括名称、简介、第一页视频的标题、链接和本地封面。每次采集共用一个浏览器窗口；仅获取第一页，不滚动翻页。图文和文章不作为视频。遇到风控停止，已有数据保留。

支持在同一批次混合抖音、快手、YouTube 和哔哩哔哩。公开 YouTube、哔哩哔哩频道通常可直接采集，无需先执行 `login`：

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter collect "https://www.youtube.com/@YOUR_HANDLE/videos" "https://space.bilibili.com/YOUR_UID/upload/video" --output data/mixed-platforms
```

将 `YOUR_HANDLE` 和 `YOUR_UID` 替换为实际账户。后续 `screen`、续跑和可视化用法与其它平台相同。

```powershell
.\.venv\Scripts\python.exe -m account_filter collect --resume data/my-dataset
```

采集续跑跳过完整账户，只重试失败或未完成项。成功采集但缺少封面的原因在账户的 `archive-status.json` 中。缺图不会触发重新访问主页。登录会话位于项目 `.browser/profile/`；不要并发使用同一会话目录。

## 2. 从采集数据筛选账户

```powershell
.\.venv\Scripts\python.exe -m account_filter screen --data data/my-dataset --config configs/api.toml --category sign-language --top-videos 5 --output results/my-experiment
```

`--config` 和 `--category` 均需明确指定，不默认选择服务商或目标类别。第一轮只看标题；第二轮看名称、简介及选中的标题、封面。频道类别由模型独立判断。`--top-videos` 默认 5；`--dry-run` 只保存第一轮请求预览。

```powershell
.\.venv\Scripts\python.exe -m account_filter screen --resume results/my-experiment
```

续跑读取已保存的数据位置、API 和类别配置，跳过成功结果，重试失败项。更换模型、规则或候选数量时使用新实验名。

结果直接保存在 `results/my-experiment/results.csv`；中间请求、响应与标题排序位于同级 `intermediate/` 中。不存在自动添加的时间子目录。已有非空目录会报错，避免覆盖。原始采集数据不会被筛选修改。

## 自定义来源

不需要平台爬虫。按照 [数据格式](data-format.zh-CN.md) 生成数据集，然后验证并使用相同的 `screen` 命令：

```powershell
.\.venv\Scripts\python.exe -m account_filter validate-data data/custom-dataset
```

## 查看结果

直接在 Edge/Chrome 中打开根目录 `analysis.html`。第一次自动展示 6 个真实公开样例；选择自己的 `results.csv` 和采集数据目录即可替换。也可添加二次人工核验 CSV；页面自动合并性能与错误分析。文件仅在本机读取，浏览器会记住上次分析。

示例是人为选择的小规模展示，不用于估计全量准确率。样例详情与公开范围见 [公开说明](../examples/real-demo/README.zh-CN.md)。

macOS/Linux 将上述解释器路径改为 `.venv/bin/python`。安装见 [安装文档](installation.zh-CN.md)，模型与类别规则见 [配置说明](configuration.zh-CN.md)。
