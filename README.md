<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a></p>

<div align="center">
  <img src="docs/assets/banner.en.svg" alt="Jev Account Filter: decision models for video-platform account screening" width="1200">
  <p><strong>Find the accounts. Build the dataset.</strong></p>
  <p>Screen video-platform accounts with decision models. Start domain dataset collection with better sources.</p>
  <p><kbd>Fast</kbd>　<kbd>Cheap</kbd>　<kbd>Accurate</kbd>　<kbd>Flexible</kbd>　<kbd>Promising</kbd></p>
  <p><a href="docs/installation.md">Installation</a> · <a href="docs/commands.md">Commands</a> · <a href="docs/configuration.md">Configuration</a> · <a href="docs/development.md">Development</a></p>
</div>

---

## Introduction

Collecting datasets from user-generated content communities is becoming an increasingly common approach to training models. Video platforms host a continuous stream of real-world content from diverse creators, offering opportunities to scale training data, broaden its distribution, and represent more people. Finding sources relevant to a specific domain within this growing collection has become an important part of dataset construction.

A common collection pipeline first identifies relevant accounts, then uses video models and human review to select individual videos suitable for training. Previous work has explored manually curated sources, automatic candidate retrieval, and channel-level sampling, yet source selection and content review still require human effort.[\[1\]](https://aclanthology.org/2022.emnlp-main.427/) [\[2\]](https://papers.nips.cc/paper_files/paper/2023/hash/5c61452daca5f0c260e683b317d13a3f-Abstract-Datasets_and_Benchmarks.html) [\[3\]](https://arxiv.org/html/2407.11144) As the number of candidate accounts grows, the cost of browsing and judging them increases. Changes to category boundaries or collection goals can also require repeating part of that work. **Account screening has therefore become a bottleneck in domain dataset collection.**

An account's profile page already provides useful previews: titles describe video topics, thumbnails supply visual cues, and the account name and biography describe the creator's focus. These signals offer a basis for inexpensive source selection. Meanwhile, decision models can turn supplied evidence directly into category choices and relevance probabilities, answering several independent questions in a single request. This makes them suitable for large-scale, repeatable screening.[\[5\]](https://developers.openai.com/api/docs/guides/decisions) [\[7\]](https://docs.typesafe.ai/introduction)

**To the best of our knowledge, Jev Account Filter is the first project to use multimodal decision models to screen video-platform accounts for domain dataset collection, relying only on video titles and thumbnails as content evidence without downloading or watching full videos.** It first selects candidates by title, then combines their thumbnails with account metadata to judge the account's category independently, turning a large pool of accounts into a reviewable list of collection sources. Collected evidence and screening rules are stored separately, allowing researchers to revise criteria, replace models, and compare results using the same cache. Accounts include both creator profiles and channels on video platforms. Sign-language screening is one validated application; other domains can be selected through category configurations.

### Contributions and advantages

<p><img src="docs/assets/contributions/fast.en.svg" alt="Fast — illustrated contribution" width="100%"></p>

<p><img src="docs/assets/contributions/cheap.en.svg" alt="Cheap — illustrated contribution" width="100%"></p>

<p><img src="docs/assets/contributions/accurate.en.svg" alt="Accurate — illustrated contribution" width="100%"></p>

<p><img src="docs/assets/contributions/flexible.en.svg" alt="Flexible — illustrated contribution" width="100%"></p>

<p><img src="docs/assets/contributions/promising.en.svg" alt="Promising — illustrated contribution" width="100%"></p>

The sources for multi-question support, speed, and pricing are the [Decisions API documentation (reference 5)](https://developers.openai.com/api/docs/guides/decisions). The official standard prices shown in the cards are dated October 14, 2026; long-context and regional-processing premiums apply. See [reference 6](https://developers.openai.com/api/docs/changelog) for the release record. Independent adjudication statistics for disagreements between the model and human annotations will be added when available.
<!-- Add independent adjudication results: model errors, original human-annotation errors, and adjudication criteria; then update the accuracy comparison. -->

## Related work

### Decision models: Jev and multimodal Decisions APIs

TypeSafe's **Jev** is designed for classification, scoring, and conditional judgments inside software. It accepts shared state and typed questions and returns choices, scores, and probabilities. Its official documentation states that multiple questions in one call can be evaluated independently and in parallel against the same input. The release announcement also discusses parallel sampling and training for calibrated decisions. These interfaces organize model judgments into composable program steps, providing a useful foundation for batch content screening.[\[7\]](https://docs.typesafe.ai/introduction) [\[8\]](https://typesafe.ai/blog/introducing-system-one-models-and-jev)

OpenAI's **Decisions API** likewise supports structured categories, condition probabilities, and scores. It accepts text and images and can evaluate several independent questions in one request.[\[5\]](https://developers.openai.com/api/docs/guides/decisions) The existing experiments in this project call **GPT-6 Luna Decisions** through OpenRouter, using its multimodal capabilities to combine titles and thumbnails. Jev is discussed here as related work on decision models. The project focuses on organizing these capabilities into an account-screening method, with explicit configurations for the model service and target category.

### Sign-language datasets: from content discovery to video-level review

**OpenASL** collects sign-language videos from three selected YouTube channels, illustrating a corpus-building approach based on manually chosen sources.[\[1\]](https://aclanthology.org/2022.emnlp-main.427/) **YouTube-ASL** broadens the source pool by retrieving candidates with platform-generated tags, followed by skilled annotators filtering individual videos.[\[2\]](https://papers.nips.cc/paper/2023/file/5c61452daca5f0c260e683b317d13a3f-Paper-Datasets_and_Benchmarks.pdf) **YouTube-SL-25** extends retrieval to multiple sign languages and improves screening efficiency through channel-level sampling and targeted audits. It also reports that three native sign-language annotators spent several months reviewing candidate videos for YouTube-ASL.[\[3\]](https://arxiv.org/html/2407.11144)

**Seeing, Signing, and Saying** uses VLMs to check person visibility, signing activity, and video–text alignment, producing TikTok-SL-8 and demonstrating the potential of model-assisted video-level curation.[\[4\]](https://aclanthology.org/2025.ranlp-1.159/) This project moves model judgments earlier, to source selection: profile-page titles and thumbnails provide an initial screen of accounts before video collection and quality review. The approach complements video-level review by reducing collection and inspection effort spent on irrelevant sources.

## Method

**Task and evidence.** Given a list of video-platform account URLs and a target category, the program collects each account's name and biography, together with the titles, URLs, and thumbnails of videos on its first page, and stores them in the canonical cache. Extraction is restricted to videos by the target creator, excluding image posts and other non-video content. Account positioning and individual works jointly provide evidence; results refer to the collected profile-page snapshot.

**Title-based candidate selection.** The first pass sends only the titles of all first-page videos to the model. Videos are ranked by their estimated relevance to the target category, and the top **N** candidates are selected. The default is **N = 5**, adjustable by task. This pass excludes the account name, biography, and thumbnails so that candidates are initially judged on their own titles, while concentrating second-pass image inputs on the most promising works.

**Multimodal account classification.** The second pass combines candidate titles and their corresponding thumbnails with the account name and biography, using complementary semantic and visual evidence to assess the account's focus. Within one request, the model independently answers questions about the account category, account probability, and each candidate video's relevance. The model selects the account category directly; no individual video's score or fixed threshold replaces that judgment. Video relevance probabilities express the strength of evidence for individual candidates. The two passes require separate model calls because the second depends on candidate selection in the first.

**Cache reuse and reviewable results.** Collected evidence is saved separately from each experiment's configuration, requests, and model responses. Complete local caches allow new experiments without revisiting the platform. A CSV summarizes account judgments, probabilities, and video links, while an HTML report provides distributions, conditional filters, and thumbnail details. Researchers can trace disagreements, revise screening criteria, and pass accepted accounts to downstream video collection and quality review.

## Experiments

Using the sign-language category configuration, we screened **2,140 Douyin accounts** and compared predictions with the original human annotations. The experiment used the off-the-shelf GPT-6 Luna Decisions model without fine-tuning. **2,136 accounts** had explicit binary annotations; the remaining **4** were annotated as uncertain and excluded from binary agreement calculations.

| Evaluation item | Result |
| --- | ---: |
| Total accounts | 2140 |
| Accounts with explicit binary human annotations | 2136 |
| Predictions matching original human annotations | 1942 |
| Binary annotation agreement | **90.92%** |

These metrics measure agreement with the original human annotations. Accounts with disagreements retain their thumbnails and judgment scores for independent adjudication. A comparison of model accuracy with the original human annotations will be added after that adjudication is complete.

## Getting started

**[Installation and environment](docs/installation.md)** · **[Commands](docs/commands.md)** · **[Configuration](docs/configuration.md)** · **[Development and testing](docs/development.md)**

Douyin and Kuaishou are currently supported. Adapters for WeChat, YouTube, TikTok, and other platforms are planned.

Installation steps, commands, and parameters are documented in the guides above. Detailed sign-language experiment procedures and records are available in the [experiment guide](docs/usage.md).

A [synthetic input CSV](input/channels.example.csv) is included for reference. Team-collected account identities, profile data, thumbnails, and experiment outputs are not distributed; see [public samples and private data](docs/installation.md#public-sample-and-private-data).

## Citing this project

If this project helps your dataset collection or research, you can use the following BibTeX entry. The author field is pending.

```bibtex
@misc{jevaccountfilter2026,
  author       = {},
  title        = {{Jev Account Filter}: Decision-Model-Based Video Platform Account Screening for Domain Dataset Collection},
  year         = {2026},
  howpublished = {Software repository},
  url          = {https://github.com/caiweihan/jev-account-filter}
}
```

## References

1. Bowen Shi, Diane Brentari, Gregory Shakhnarovich, and Karen Livescu. **[Open-Domain Sign Language Translation Learned from Online Video](https://aclanthology.org/2022.emnlp-main.427/)**. EMNLP, 2022.
2. Dave Uthus, Garrett Tanzer, and Manfred Georg. **[YouTube-ASL: A Large-Scale, Open-Domain American Sign Language-English Parallel Corpus](https://papers.nips.cc/paper_files/paper/2023/hash/5c61452daca5f0c260e683b317d13a3f-Abstract-Datasets_and_Benchmarks.html)**. NeurIPS, 2023.
3. Garrett Tanzer and Biao Zhang. **[YouTube-SL-25: A Large-Scale, Open-Domain Multilingual Sign Language Parallel Corpus](https://arxiv.org/abs/2407.11144)**. arXiv:2407.11144, 2024.
4. Shakib Yazdani, Yasser Hamidullah, Cristina España-Bonet, and Josef van Genabith. **[Seeing, Signing, and Saying: A Vision-Language Model-Assisted Pipeline for Sign Language Data Acquisition and Curation from Social Media](https://aclanthology.org/2025.ranlp-1.159/)**. RANLP, 2025.
5. OpenAI. **[Decisions API Guide](https://developers.openai.com/api/docs/guides/decisions)**. Accessed October 14, 2026.
6. OpenAI. **[API Changelog — October 6, 2026](https://developers.openai.com/api/docs/changelog)**. GPT-6 Luna Decisions release record.
7. TypeSafe AI. **[Jev / System One Models: Introduction](https://docs.typesafe.ai/introduction)**. Accessed October 15, 2026.
8. Diogo Almeida. **[Introducing System One Models & Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)**. TypeSafe AI, 2026.
