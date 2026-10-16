[English](README.md) | [简体中文](README.zh-CN.md)

# Real demonstration subset

Six public Douyin accounts are deliberately selected from the existing experiment: two original agreements in each binary class and two disagreements. Account names, biographies, titles, URLs, thumbnail contents, and original model scores are real. Each account includes only its five previously selected candidates, not the full first page. Thumbnails are re-encoded as JPEG for packaging; no new collection or inference was performed.

This subset is explicitly authorized for publication. It excludes the remaining team dataset, full model requests/responses, credentials, browser sessions, and local filesystem paths. Human labels are the original experiment annotations; the optional second-review CSV contains only these selected accounts. Examples are illustrative and must not be used to estimate population accuracy.

`data/` follows the version 1 dataset contract; `results.csv` contains original results. The standalone root viewer embeds this same subset for first-use analysis without a server or network request.
