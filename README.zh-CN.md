<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a></p>

<div align="center">
  <img src="docs/assets/banner.svg" alt="Jev Account Filter：用决策模型筛选视频平台账户" width="1200">
  <p><strong>Find the accounts. Build the dataset.</strong></p>
  <p>用决策模型筛选视频平台账户，让领域数据集采集从更好的来源开始。</p>
  <p><kbd>Fast</kbd>　<kbd>Cheap</kbd>　<kbd>Accurate</kbd>　<kbd>Flexible</kbd>　<kbd>Promising</kbd></p>
  <p><a href="docs/installation.zh-CN.md">安装</a> · <a href="docs/commands.zh-CN.md">运行指南</a> · <a href="docs/configuration.zh-CN.md">配置说明</a> · <a href="docs/development.zh-CN.md">扩展</a></p>
</div>

---

## 引言

从用户创作社区采集数据集，用于模型训练，正在成为越来越常见的研究路径。视频平台汇集了大量创作者持续发布的真实场景内容，为扩大训练数据规模、丰富内容分布和覆盖更多人群提供了机会。如何从这些持续增长的内容中找到特定领域的数据来源，也随之成为数据集构建的重要问题。

一条常见的采集路线是先确定相关账户，再通过视频模型和人工检查，筛出其中适合训练的具体视频。已有研究尝试了人工整理来源、自动检索候选和按频道抽查等方法，但筛选来源及审核内容仍需要投入人工。[\[1\]](https://aclanthology.org/2022.emnlp-main.427/) [\[2\]](https://papers.nips.cc/paper_files/paper/2023/hash/5c61452daca5f0c260e683b317d13a3f-Abstract-Datasets_and_Benchmarks.html) [\[3\]](https://arxiv.org/html/2407.11144) 候选账户越多，逐个浏览和判断的成本就越高；当类别边界或采集目标改变时，部分工作还需要重做。**账户筛选因此成为领域数据采集中的一道瓶颈。**

账户主页本身已经提供了丰富的预览信息：标题表达作品主题，封面呈现视觉线索，名称和简介补充创作者定位。这些信息为低成本的来源判断提供了可能。与此同时，决策模型能够把给定证据直接转换为类别选择和相关性概率，并在同一请求中回答多个独立问题，适合大规模、可重复的筛选任务。[\[5\]](https://developers.openai.com/api/docs/guides/decisions) [\[7\]](https://docs.typesafe.ai/introduction)

**据我们所知，Jev Account Filter 是首个将多模态决策模型用于领域数据集采集中的视频平台账户筛选的项目，仅以视频标题和封面提供作品证据，无需下载或逐个观看完整视频。** 项目先根据标题选择候选，再结合候选封面与账户资料独立判断账户类别，将大量备选账户转化为可采集、可复核的来源清单。采集资料与筛选规则分别保存，研究者可以在同一份缓存上反复调整判据、替换模型并比较结果。这里的账户包括视频平台的创作者账号与频道；手语筛选是已经验证的一项应用，其他领域可通过类别配置接入。

### 贡献与优势

<p><img src="docs/assets/contributions/fast.svg" alt="Fast — 图文贡献卡片" width="100%"></p>

<p><img src="docs/assets/contributions/cheap.svg" alt="Cheap — 图文贡献卡片" width="100%"></p>

<p><img src="docs/assets/contributions/accurate.svg" alt="Accurate — 图文贡献卡片" width="100%"></p>

<p><img src="docs/assets/contributions/flexible.svg" alt="Flexible — 图文贡献卡片" width="100%"></p>

<p><img src="docs/assets/contributions/promising.svg" alt="Promising — 图文贡献卡片" width="100%"></p>

决策接口的多问题能力、速度与价格依据见 [Decisions API 文档（参考文献 5）](https://developers.openai.com/api/docs/guides/decisions)；卡片中的官方标准价格截至 2026-10-14，长上下文与区域处理另有加价。发布记录见 [参考文献 6](https://developers.openai.com/api/docs/changelog)。人工与模型差异的独立复核统计将在完成后补充。
<!-- 待补充独立复核结果：模型错误数、原人工标注错误数与复核标准；据此更新准确性比较。 -->

## 相关工作

### 决策模型：Jev 与多模态 Decisions 接口

TypeSafe 的 **Jev** 围绕软件中的分类、评分与条件判断设计，接受共享状态和带类型的问题，返回选项、分数及概率。其官方文档说明，同一次调用中的多个问题可以针对同一输入并行、独立地评估；发布介绍进一步讨论了并行采样与面向校准决策的训练方法。这类接口将模型判断组织成可组合的程序步骤，为批量内容筛选提供了适合的技术基础。[\[7\]](https://docs.typesafe.ai/introduction) [\[8\]](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

OpenAI 的 **Decisions API** 同样支持结构化的类别、条件概率和评分，并能够接收文本与图像、在一次请求中评估多个独立问题。[\[5\]](https://developers.openai.com/api/docs/guides/decisions) 本项目的既有实验通过 OpenRouter 调用 **GPT-6 Luna Decisions**，利用其多模态判断能力融合视频标题与封面；Jev 在此作为决策模型的相关工作介绍。项目关注如何把这类能力组织为账户筛选方法，并通过显式配置选择模型服务与筛选类别。

### 手语数据集：从内容发现到逐视频审核

**OpenASL** 从三个选定的 YouTube 频道采集手语视频，代表了围绕人工确定来源构建语料的路线。[\[1\]](https://aclanthology.org/2022.emnlp-main.427/) **YouTube-ASL** 进一步使用平台自动标签检索候选，再由熟练标注者逐视频筛选，扩大了内容来源范围。[\[2\]](https://papers.nips.cc/paper/2023/file/5c61452daca5f0c260e683b317d13a3f-Paper-Datasets_and_Benchmarks.pdf) **YouTube-SL-25** 将检索扩展到多种手语，并通过按频道抽查与定向审阅提高筛选效率；论文也指出，YouTube-ASL 的三名母语手语标注者曾花费数月审核候选视频。[\[3\]](https://arxiv.org/html/2407.11144)

**Seeing, Signing, and Saying** 引入 VLM 辅助检查人物可见性、手语活动及视频与文本的匹配，并构建 TikTok-SL-8，展示了模型辅助逐视频整理数据的潜力。[\[4\]](https://aclanthology.org/2025.ranlp-1.159/) 本项目将模型判断前移到来源选择阶段，以账户主页的标题与封面进行预筛，为后续视频采集和质量检查提供候选账户。这一方法与逐视频审核相互衔接，目标是减少在无关来源上投入的采集和检查成本。

## 方法

**任务与证据。** 给定一批视频平台账户链接和一个目标类别，程序采集账户名称、简介，以及第一页视频的标题、链接与封面，并保存到正式缓存。作品提取限定为目标作者的视频，排除图文等非视频作品。账户定位和具体作品共同构成判断依据，筛选结果对应这批已采集的主页证据。

**基于标题的候选选择。** 第一轮只将第一页全部视频的标题输入模型，按与目标类别的相关性概率排序，选出最相关的前 **N** 个候选，默认 **N = 5**，可按任务调整。这一步不输入账户名称、简介或封面，让候选首先依据作品自身的标题接受判断，并将第二轮的图像输入集中在最有价值的作品上。

**多模态账户判别。** 第二轮将候选视频的标题、对应封面以及账户名称、简介共同输入模型，以互补的语义和视觉线索评估账户定位。在同一请求中，模型分别回答账户类别、账户概率与各候选视频相关性等独立问题。账户类别由模型直接判断，不用某个视频的分数或固定阈值替代；各视频的相关性概率用于展示具体作品的证据强弱。两轮之间存在候选选择依赖，因此分别调用模型。

**缓存复用与结果复核。** 程序将采集资料与每次实验的配置、请求和模型响应分别保存，支持在不重新访问平台的情况下，基于完整本地缓存重新实验。CSV 汇总账户判断、概率与视频链接，HTML 报告提供分布分析、条件筛选和封面详情。研究者可以追溯差异、调整筛选标准，并将接受的账户交给后续视频采集与质量审核流程。

## 实验

我们使用手语类别配置，对 **2140 个抖音账户**进行筛选，并与原人工标注比较。实验直接使用现成的 GPT-6 Luna Decisions，未进行模型微调。二类标注明确的账户共 **2136 个**，其余 **4 个**人工标注为疑难，未纳入二类一致率计算。

| 评估项 | 结果 |
| --- | ---: |
| 账户总数 | 2140 |
| 人工二类标注明确的账户 | 2136 |
| 预测与原人工标注一致 | 1942 |
| 二类标注一致率 | **90.92%** |

上述指标衡量预测与原人工标注的一致程度。两者不一致的账户保留对应封面与判断分数，供独立复核；模型与原人工标注的准确性比较将在复核完成后补充。

## 开始使用

**[安装与环境](docs/installation.zh-CN.md)** · **[运行指南](docs/commands.zh-CN.md)** · **[配置说明](docs/configuration.zh-CN.md)** · **[扩展与测试](docs/development.zh-CN.md)**

目前支持抖音、快手，后续计划适配微信、YouTube、TikTok 等平台。

具体安装步骤、命令和参数放在上述文档中。手语实验的详细流程与记录见 [实验说明](docs/usage.zh-CN.md)。

仓库提供[虚构输入CSV样例](input/channels.example.csv)供参考。团队收集的真实账号身份、主页资料、封面和实验输出不随项目公开，详见[公开样例与私有数据](docs/installation.zh-CN.md#公开样例与私有数据)。

## 引用本项目

如果本项目帮助了你的数据集采集或研究，可以使用以下 BibTeX。作者署名待补充。

```bibtex
@misc{jevaccountfilter2026,
  author       = {},
  title        = {{Jev Account Filter}: Decision-Model-Based Video Platform Account Screening for Domain Dataset Collection},
  year         = {2026},
  howpublished = {Software repository},
  url          = {https://github.com/caiweihan/jev-account-filter}
}
```

## 参考文献

1. Bowen Shi, Diane Brentari, Gregory Shakhnarovich, and Karen Livescu. **[Open-Domain Sign Language Translation Learned from Online Video](https://aclanthology.org/2022.emnlp-main.427/)**. EMNLP, 2022.
2. Dave Uthus, Garrett Tanzer, and Manfred Georg. **[YouTube-ASL: A Large-Scale, Open-Domain American Sign Language-English Parallel Corpus](https://papers.nips.cc/paper_files/paper/2023/hash/5c61452daca5f0c260e683b317d13a3f-Abstract-Datasets_and_Benchmarks.html)**. NeurIPS, 2023.
3. Garrett Tanzer and Biao Zhang. **[YouTube-SL-25: A Large-Scale, Open-Domain Multilingual Sign Language Parallel Corpus](https://arxiv.org/abs/2407.11144)**. arXiv:2407.11144, 2024.
4. Shakib Yazdani, Yasser Hamidullah, Cristina España-Bonet, and Josef van Genabith. **[Seeing, Signing, and Saying: A Vision-Language Model-Assisted Pipeline for Sign Language Data Acquisition and Curation from Social Media](https://aclanthology.org/2025.ranlp-1.159/)**. RANLP, 2025.
5. OpenAI. **[Decisions API Guide](https://developers.openai.com/api/docs/guides/decisions)**. 访问日期：2026-10-14。
6. OpenAI. **[API Changelog — October 6, 2026](https://developers.openai.com/api/docs/changelog)**. GPT-6 Luna Decisions 发布记录。
7. TypeSafe AI. **[Jev / System One Models: Introduction](https://docs.typesafe.ai/introduction)**. 访问日期：2026-10-15。
8. Diogo Almeida. **[Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)**. TypeSafe AI，2026。
