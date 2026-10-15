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

<p><img src="docs/assets/collection-workflow.en.svg" alt="Discover candidate accounts via keywords and recommendations → manually screen relevant accounts (account-screening bottleneck) → select videos with video models and human review → preprocess and build the training dataset. Below, Jev Account Filter screens accounts via titles and thumbnails, with an upward arrow pointing to manual account screening." width="100%"></p>

An account's profile page already provides useful previews: titles describe video topics, thumbnails supply visual cues, and the account name and biography describe the creator's focus. These signals offer a basis for inexpensive source selection. Meanwhile, decision models can turn supplied evidence directly into category choices and relevance probabilities, answering several independent questions in a single request. This makes them suitable for large-scale, repeatable screening.[\[5\]](https://developers.openai.com/api/docs/guides/decisions) [\[7\]](https://docs.typesafe.ai/introduction)

**To the best of our knowledge, Jev Account Filter is the first project to screen video-platform accounts for domain dataset collection using only video titles and thumbnails as content evidence, without downloading or watching full videos.** It first selects candidates by title, then combines their thumbnails with account metadata to judge the account's category independently, turning a large pool of accounts into a reviewable list of collection sources. Collected evidence and screening rules are stored separately, allowing researchers to revise criteria, replace models, and compare results using the same cache. Accounts include both creator profiles and channels on video platforms. Sign-language screening is one validated application; other domains can be selected through category configurations.

### Contributions and advantages

We validated this workflow on **2,140 Douyin accounts** using the sign-language category configuration and the off-the-shelf **GPT-6 Luna Decisions** model, without fine-tuning.

<p><img src="docs/assets/contributions/fast.en.svg" alt="Fast: 2,140 accounts, 1,500 human person-hours versus 11 model hours, a 136.36-fold speedup; multiple questions answered in parallel." width="100%"></p>

<details>
<summary>Time comparison</summary>

The team reports **1,500 person-hours** of human screening effort and **11 hours** of model screening time, giving `1500 / 11 ≈ 136.36`. Person-hours measure total human effort; parallel human work would have a different elapsed duration.

</details>

<p><img src="docs/assets/contributions/cheap.en.svg" alt="Cheap: both models have a Standard input rate of $0.10 per million tokens; gpt-6-luna output costs $0.50 per million tokens, while gpt-6-luna-decisions has no output charge." width="100%"></p>

<details>
<summary>Pricing comparison and sources</summary>

Prices are official Standard rates as of **October 16, 2026**, from the [GPT-6 Luna model documentation (reference 9)](https://developers.openai.com/api/docs/models/gpt-6-luna) and the [Decisions API documentation (reference 5)](https://developers.openai.com/api/docs/guides/decisions); long-context and regional-processing premiums apply. The chart's `gpt-6-luna-decisions` denotes the decision model called through the official API as `gpt-6-luna`. Input and output bars compare per-token rates separately, rather than total experiment costs.

</details>

<p><img src="docs/assets/contributions/accurate.en.svg" alt="Accurate: conditional full-set accuracy estimates of 94.02% for human labels and 96.64% for model predictions; the vertical axis spans 90% to 100%." width="100%"></p>

<details>
<summary>Second-review results and accuracy definitions</summary>

All **198 accounts** on which the model and original human annotations disagreed underwent a second human review, whose labels serve as the reference. The remaining **1,942 accounts**, where the model and original annotations agree, are assumed to have correct original labels. Under this conditional full-set estimate, the original human annotations are correct on **2012 / 2140** accounts, with **128 errors** and **94.02%** accuracy. The model is correct on **2068 / 2140** accounts, with **72 errors** and **96.64%** accuracy.

These figures compare both sources against the second-review reference. Because matching accounts were not independently re-reviewed, they are not independently verified full-set accuracies.

</details>

<p><img src="docs/assets/contributions/flexible.en.svg" alt="Flexible — illustrated contribution" width="100%"></p>

<p><img src="docs/assets/contributions/promising.en.svg" alt="Promising — illustrated contribution" width="100%"></p>

## Application domains

Selecting consistent sources from domain-specific accounts can support UGC dataset collection across multiple fields. Sign language is the application validated in this project; the other domains are potential extensions. Dataset names below are limited to papers that describe selected channel sources or human review at channel level. Expand the evidence notes for the original wording.

<p><img src="docs/assets/application-domains.en.svg" alt="Five horizontal rounded cards, each with an emoji: sign language (OpenASL, YouTube-ASL, YouTube-SL-25), instrument performance (PIAST), makeup tutorials (YouMakeup), dance, and fitness training." width="100%"></p>

<details>
<summary>Paper evidence: channel sources and human screening</summary>

**[OpenASL](https://aclanthology.org/2022.emnlp-main.427.pdf#page=3) · §3.** The authors chose three YouTube sources. The text refers to “in these two channels” before describing the third source. YouTube-ASL [§2.1](https://papers.nips.cc/paper/2023/file/5c61452daca5f0c260e683b317d13a3f-Paper-Datasets_and_Benchmarks.pdf#page=2) characterizes the OpenASL approach as “manual channel curation”.

**[YouTube-ASL](https://papers.nips.cc/paper/2023/file/5c61452daca5f0c260e683b317d13a3f-Paper-Datasets_and_Benchmarks.pdf#page=4) · §3.2.** Candidates were retrieved using automatic tags. Human annotators could apply a judgment to a whole channel: “labels held for an entire channel of videos”. Its human component therefore includes channel-level review.

**[YouTube-SL-25](https://arxiv.org/html/2407.11144#S2.SS2) · §2.2.** The author sampled videos per channel before accepting, rejecting, or investigating that channel: “For each channel, the author sampled several random videos”.

**[PIAST](https://arxiv.org/html/2411.02551v2#S2.SS2) · §2.2.** The authors combined tag-based retrieval with “23 selected channels known for their piano content”. The paper describes researcher-selected sources without detailing each channel-screening decision. After preprocessing, the dataset primarily provides audio, transcribed MIDI, and text.

**[YouMakeup](https://aclanthology.org/anthology-files/pdf/D/D19/D19-1517.pdf#page=4) · §3.1.** The authors compiled a list of cosmetic brands and beauty bloggers before collecting tutorials from their official channels: “we search their official channels on the YouTube”. This places source selection before collecting individual works.

</details>

## Method

**Task and evidence.** Given a list of video-platform account URLs and a target category, the program collects each account's name and biography, together with the titles, URLs, and thumbnails of videos on its first page, and stores them in the canonical cache. Extraction is restricted to videos by the target creator, excluding image posts and other non-video content. Account positioning and individual works jointly provide evidence; results refer to the collected profile-page snapshot.

**Title-based candidate selection.** The first pass sends only the titles of all first-page videos to the model. Videos are ranked by their estimated relevance to the target category, and the top **N** candidates are selected. The default is **N = 5**, adjustable by task. This pass excludes the account name, biography, and thumbnails so that candidates are initially judged on their own titles, while concentrating second-pass image inputs on the most promising works.

**Multimodal account classification.** The second pass combines candidate titles and their corresponding thumbnails with the account name and biography, using complementary semantic and visual evidence to assess the account's focus. Within one request, the model independently answers questions about the account category, account probability, and each candidate video's relevance. The model selects the account category directly; no individual video's score or fixed threshold replaces that judgment. Video relevance probabilities express the strength of evidence for individual candidates. The two passes require separate model calls because the second depends on candidate selection in the first.

**Cache reuse and reviewable results.** Collected evidence is saved separately from each experiment's configuration, requests, and model responses. Complete local caches allow new experiments without revisiting the platform. A CSV summarizes account judgments, probabilities, and video links, while an HTML report provides distributions, conditional filters, and thumbnail details. Researchers can trace disagreements, revise screening criteria, and pass accepted accounts to downstream video collection and quality review.

## Getting started

**[Installation and environment](docs/installation.md)** · **[Commands](docs/commands.md)** · **[Configuration](docs/configuration.md)** · **[Development and testing](docs/development.md)**

To inspect existing results, open [`analysis.html`](analysis.html) and select a CSV and optional external cache folders. Reuse the same page for different experiments without starting a server or regenerating reports.

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
4. Hayeon Bang, Eunjin Choi, Megan Finch, Seungheon Doh, Seolhee Lee, Gyeong-Hoon Lee, and Juhan Nam. **[PIAST: A Multimodal Piano Dataset with Audio, Symbolic and Text](https://arxiv.org/abs/2411.02551)**. NLP4MusA, 2024.
5. OpenAI. **[Decisions API Guide](https://developers.openai.com/api/docs/guides/decisions)**. Accessed October 14, 2026.
6. OpenAI. **[API Changelog — October 6, 2026](https://developers.openai.com/api/docs/changelog)**. GPT-6 Luna Decisions release record.
7. TypeSafe AI. **[Jev / System One Models: Introduction](https://docs.typesafe.ai/introduction)**. Accessed October 15, 2026.
8. Weiying Wang, Yongcheng Wang, Shizhe Chen, and Qin Jin. **[YouMakeup: A Large-Scale Domain-Specific Multimodal Dataset for Fine-Grained Semantic Comprehension](https://aclanthology.org/D19-1517/)**. EMNLP-IJCNLP, 2019.
9. OpenAI. **[GPT-6 Luna — Model and Pricing](https://developers.openai.com/api/docs/models/gpt-6-luna)**. Accessed October 16, 2026.
