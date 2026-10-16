<p align="center"><a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a></p>

<div align="center">
  <img src="docs/assets/banner.en.svg" alt="Jev Account Filter: decision models for video-platform account screening" width="1200">
  <p><strong>Find the accounts. Build the dataset.</strong></p>
  <p>Screen video-platform accounts with decision models. Start domain dataset collection with better sources.</p>
  <p><kbd>Fast</kbd>　<kbd>Cheap</kbd>　<kbd>Accurate</kbd>　<kbd>Flexible</kbd>　<kbd>Promising</kbd></p>
  <p><a href="docs/installation.md">Installation</a> · <a href="docs/commands.md">Commands</a> · <a href="docs/configuration.md">Configuration</a></p>
</div>

---

## Introduction

Collecting datasets from user-generated content communities is becoming an increasingly common approach to training models. Video platforms host a continuous stream of real-world content from diverse creators, offering opportunities to scale training data, broaden its distribution, and represent more people. Finding sources relevant to a specific domain within this growing collection has become an important part of dataset construction.

A common collection pipeline first identifies relevant accounts, then uses video models and human review to select individual videos suitable for training. Previous work has explored manually curated sources, automatic candidate retrieval, and channel-level sampling, yet source selection and content review still require human effort.   As the number of candidate accounts grows, the cost of browsing and judging them increases. Changes to category boundaries or collection goals can also require repeating part of that work. **Account screening has therefore become a bottleneck in domain dataset collection.**

<p><img src="docs/assets/collection-workflow.en.svg" alt="Discover candidate accounts via keywords and recommendations → manually screen relevant accounts (account-screening bottleneck) → select videos with video models and human review → preprocess and build the training dataset. Below, Jev Account Filter screens accounts via titles and thumbnails, with an upward arrow pointing to manual account screening." width="100%"></p>

An account's profile page already provides useful previews: titles describe video topics, thumbnails supply visual cues, and the account name and biography describe the creator's focus. These signals offer a basis for inexpensive source selection. Meanwhile, decision models can turn supplied evidence directly into category choices and relevance probabilities, answering several independent questions in a single request. This makes them suitable for large-scale, repeatable screening.

**To the best of our knowledge, Jev Account Filter is the first project to screen video-platform accounts for domain dataset collection using only video titles and thumbnails as content evidence, without downloading or watching full videos.** It first selects candidates by title, then combines their thumbnails with account metadata to judge the account's category independently, turning a large pool of accounts into a reviewable list of collection sources. Collected evidence and screening rules are stored separately, allowing researchers to revise criteria, replace models, and compare results using the same collected data. Accounts include both creator profiles and channels on video platforms. Sign-language screening is one validated application; other domains can be selected through category configurations.

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

Prices are official Standard rates as of **October 16, 2026**, from the [GPT-6 Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna) and the [Decisions API documentation](https://developers.openai.com/api/docs/guides/decisions); long-context and regional-processing premiums apply. The chart's `gpt-6-luna-decisions` denotes the decision model called through the official API as `gpt-6-luna`. Input and output bars compare per-token rates separately, rather than total experiment costs.

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

## Supported platforms

<p><img src="docs/assets/supported-platforms.en.svg" alt="Douyin, Kuaishou, YouTube, Bilibili, and custom datasets supported" width="100%"></p>

Collection adapters and category rules are independent. Custom sources only need to follow the [data format](docs/data-format.md); a platform adapter is unnecessary.

## Method

<p><img src="docs/assets/method.en.svg" alt="Method: collect account data → rank video titles → classify accounts with multimodal evidence → analyze results and refine the prompt. A left-side feedback arrow returns from the final step to the second, reusing collected data." width="100%"></p>

Collection and screening run independently: `collect` turns `input` into structured `data`; `screen` produces `results` from `data`, contacting only the selected model API. Custom sources following the [data format](docs/data-format.md) can start at the second box. Two sequential model calls select candidates and classify accounts. Reuse the same collected dataset after revising the prompt, compare experiments, and pass accepted accounts to downstream video collection and quality review.

## Visual analysis

Screening produces more than an account list. The interactive analysis page brings together class composition, classification performance, score distributions, and feature clusters. Select a group in a chart to inspect individual accounts, candidate titles, thumbnails, and model scores. Adding a second-review CSV automatically updates the evaluation reference and enables a comparison of human annotation errors and model errors.

The statistical views below come from the complete experiment on **2,140 Douyin accounts**; account-level evidence uses the explicitly published demo subset. The team's full account list and collected works remain private.

**Dataset composition and performance.** Class proportions describe the sample, while the reviewed comparison separates model errors from original annotation errors. Accuracy is a conditional estimate: the 198 original disagreements use second-review labels, and the remaining 1,942 agreements retain their original labels, assumed correct without independent review.

<p><img src="docs/assets/visualization/overview.en.png" alt="Class composition and performance across 2,140 accounts: conditional human accuracy of 94.02% and model accuracy of 96.64%." width="100%"></p>

**Errors and score distributions.** The confusion matrix separates missed accounts from false inclusions. Normalized histograms compare account probabilities for human-error and model-error samples, helping identify score ranges that warrant closer review. The two error groups can overlap.

<p><img src="docs/assets/visualization/distributions.en.png" alt="Confusion matrix against the reviewed reference, and account-probability distributions for human and model errors." width="100%"></p>

**Clusters of model outputs.** The predicted category and five candidate-video scores describe groups with different evidence profiles. The scatter plot shows a PCA projection; group panels report mean video scores and within-group error rates. Accounts missing any of the five scores are excluded without zero imputation. Clustering describes the results without changing the classification rules.

<p><img src="docs/assets/visualization/clusters.en.png" alt="Five clusters of 1,957 accounts with complete features, alongside mean video scores and error rates for each group." width="100%"></p>

**Human annotation and model error profiles.** Compare within-group error rates by reference category, feature cluster, or highest video score. The two grouping views below show that the model does not outperform humans in every score range; differences in intermediate-score groups can help prioritize further review. The same conditional evaluation reference applies.

<p><img src="docs/assets/visualization/error-features.en.png" alt="Full-experiment human and model error profiles, grouped by reference category and highest video score." width="100%"></p>

**Account evaluation and supporting evidence.** Original annotations, second reviews, current reference labels, and model predictions are shown side by side to distinguish annotation errors from model errors. This partial view shows three explicitly published accounts and one account's five candidate titles, thumbnails, and scores. The interactive page supports filtering and opening other records.

<p><img src="docs/assets/visualization/account-evidence.en.png" alt="Evaluation results for three public demo accounts, plus five candidate thumbnails, video titles, and model scores for Tianya Sign Language." width="100%"></p>

Opening [`analysis.html`](analysis.html) first displays **six real public examples**. Select your own result CSV and optional external data folders to analyze different experiments in the same page, without starting a server or regenerating reports. Statistical figures above use the full experiment; the account screenshot and default interactive demo use the public subset.

## Getting started

**[Installation and environment](docs/installation.md)**: prepare the local Python environment and browser.
**[Configuration](docs/configuration.md)**: choose a provider, model, and target category.

[Commands](docs/commands.md) · [Data format](docs/data-format.md)
