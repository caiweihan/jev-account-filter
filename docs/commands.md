[English](commands.md) | [简体中文](commands.zh-CN.md)

# Commands

Run these commands in PowerShell from the project root. Classification requires explicit `--config` and `--category` selections; the program does not assume a provider or target category.

## New classification experiment

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --top-videos 5 --output output/my-experiment
.\.venv\Scripts\python.exe -X utf8 -m account_filter run "真实频道主页链接" --config "configs/我的API.toml" --category "configs/categories/我的类别.toml"
```

Prepare the configuration files first; see [Configuration](configuration.md). `--platform auto` identifies the platform from each URL and supports mixed Douyin and Kuaishou inputs. You can also specify `douyin` or `kuaishou`. Platform detection is independent of the classification category.

Input CSVs require `主页网址` (profile URL). Optional columns are `平台` (platform), `账户昵称` (account nickname), and `人工标注` (human annotation); `审核结果` and `真实标签` are also accepted for labels. Positive and negative labels are defined by the category configuration; `1/0/-1` values are accepted too. Human annotations are used only for comparison after inference.

See [`input/channels.example.csv`](../input/channels.example.csv) for a public format example. All accounts are fictional; replace its profile URLs before running. The team's real input files are not distributed with the repository.

## New experiment using only cached evidence

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --from-cache --config "configs/我的API.toml" --category "configs/categories/我的类别.toml" --output output/new-experiment
```

This does not visit the platform or thumbnail CDN, but still calls the explicitly selected model. New experiments do not reuse previous model answers.

## A concrete example: sign-language screening

This command explicitly selects an existing service configuration and sign-language rules. These are not project defaults:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/抖音全部频道.csv" --from-cache --config configs/api.toml --category sign-language --top-videos 5 --output output/sign-language-next
```

## Resume

New experiments save `category.json` and `api-config.json`. When these snapshots exist, you do not need to repeat the selections:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/实验/时间目录"
```

The command reads the configuration explicitly selected for that experiment, rather than a system default. For older experiments without snapshots, supply the configuration explicitly:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/douyin-v7/20261014-113151-009297" --config configs/api.toml --category sign-language --top-videos 5
```

Successful entries are skipped, failed and incomplete entries are retried, and the same CSV is updated. Create a new experiment when changing the target category.

## Collection only / cache refresh

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter collect "真实频道主页链接"
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --input-csv "input/数据集.csv" --refresh-cache --login-timeout 600 --output output/cache-refresh
.\.venv\Scripts\python.exe -X utf8 -m account_filter batch --resume "output/cache-refresh/实际时间目录"
```

Collection-only runs need neither model nor category configuration and do not call the API. New browser sessions use `.browser/profile/`; explicitly add `--browser-dir .browser/kuaishou` to reuse an old session.

## Visualization

Open [`analysis.html`](../analysis.html) in the project root with Edge or Chrome. No server or Python process is needed:

1. Choose the experiment's `results.csv`. Encoding is detected automatically; the category is matched to configured labels or an exact experiment configuration. Only ambiguous cases require the collapsed analysis settings to select a category or custom positive/negative labels.
2. Optionally add `data/channels/` or an external folder with the same cache structure to display biographies, candidate titles, and thumbnails.
3. Add the experiment's entire timestamp directory for first-pass title scores, original snapshots, or an existing independent thumbnail audit. You can add multiple folders in separate selections. A matching experiment's `category.json` restores the category if none has been selected.
4. Choose another CSV to switch experiments; reselect a CSV after editing it. Each load resets chart filters.
5. Optionally load a second-review CSV to compare original human annotations and model predictions within the same performance summaries, confusion matrix, error distributions, and account table. Clearing it restores original-label agreement analysis.

Selections are remembered by default: results CSV, review CSV, multiple cache folders, category, and encodings. The browser also saves the last analysis and its used thumbnails. Reopening the same HTML directly displays that analysis without a restore click. When read permission remains valid, latest files are loaded automatically; otherwise the previous analysis is shown with its cache time. Use “更新本地文件” (update local files) only to synchronize newer disk changes, granting access if the browser requires it. “忘记上次选择” (forget previous selection) removes saved choices and browser snapshots while keeping the current analysis open.

Automatic file rereading requires Edge / Chrome with File System Access support; restoring an analysis snapshot requires available browser storage with sufficient space. Only data and thumbnails used by the analysis are cached, not the entire cache directory. Data is neither uploaded nor embedded in the HTML. Use the same browser and HTML path; private browsing and clearing browser data can remove saved state. Without file-handle support, regular file selection is used and saved analysis snapshots still restore, but changed disk files need to be selected again.

Opening the local `analysis.html` directly (`file://`) uses regular file inputs by default: a browser may expose native pickers but still reject `getFile()`. Native handles saved by older releases are not reread in this mode. The last analysis, second review, and used thumbnails still restore automatically; reselect files to read new disk changes. When served as a web page, denied native reads reveal regular file inputs while retaining existing analysis. Individual unreadable cache entries are skipped with a notice instead of failing the entire folder.

The file controls scroll with the whole page, and added folder names remain visible rather than relying on native input filenames. Category and encoding settings are collapsed by default. Automatic decoding tries UTF-8 then GB18030, and recognizes BOM-marked UTF-16. Manual settings are overrides for ambiguous data or troubleshooting; they never modify the input files.

The page starts with full-dataset human-label and prediction proportions, separately counting missing annotations, uncertain labels, and invalid predictions. Performance, score distributions, feature clusters, error types, and evidence then share one evaluation workflow.

Clustering uses the prediction category and video scores 1–5. Category one-hot encoding gives differing categories a squared distance of 1; scores remain on their original 0–1 scale. Deterministic K-means defaults to five clusters, adjustable from two to eight, capped by the number of distinct feature vectors. Only valid predictions with all five scores participate; missing scores are not filled with zero. PCA is used only for the two-dimensional display, with explained variance shown. Cluster tables expose overlapping points. Human annotations are not clustering inputs, and predictions remain unchanged.

Second reviews support the annotation-table layout `平台,账户id,账户昵称,主页网址,审核结果`; the minimum is `主页网址,审核结果`. The aliases `频道网址` and `二次标注` / `人工标注` are accepted. ID-only reviews require an account-ID column in the results CSV too. Numeric labels `1/0/-1` map to the current category's positive, uncertain, and negative classes. Review-file encoding is detected independently and can be overridden in settings.

With valid second reviews, the default comparison uses the same reviewed cohort for both accuracies: original annotations versus second labels for human accuracy, and model predictions versus second labels for model accuracy. Reference labels, original annotations, and predictions must all belong to the configured label set. Error rates can be compared by reference class, feature cluster, or maximum-score range, with account filters for human errors, model errors, and errors by both. Errors may overlap. Original labels, second labels, and predictions remain side by side in one table.

The evaluation reference switches between full original-label agreement, reviewed-subset accuracy, and a full-dataset conditional estimate using second labels where available. The last mode assumes unreviewed original labels are correct and is not independently verified full-dataset accuracy. Reviewing only original disagreements cannot support population-wide accuracy estimates. Conflicting, unknown, or ambiguous review records appear under evaluation methods and data quality; CSV changes rematch by identity rather than row number. Legacy task-specific rule simulations explicitly retain original-label scope. All changes affect presentation only, never source results.

Files are read locally in your browser, without uploads, platform/model requests, or changes to CSVs and caches. The browser can only read folders you explicitly select; thumbnails in a separate canonical cache require selecting that folder too. Channels and videos are matched by URL, and ambiguous duplicate thumbnails remain missing. CSV statistics work without caches; biographies, titles, thumbnails, and first-pass scores are not inferred from CSV fields. UTF-8 and GB18030 / GBK encodings are supported.

The supplied `analysis.html` contains no experiment data. After modifying category configurations or report templates, rebuild it once; the resulting page can still load different CSVs repeatedly:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.viewer
```

The previous command remains available for exporting an HTML snapshot containing a fixed set of results:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/实验/时间目录/results.csv"
```

Classification labels are read from that experiment's `category.json`. If an older experiment has no snapshot, provide `--category`, for example:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.report "output/douyin-v7/20261014-113151-009297/results.csv" --category sign-language
```

An HTML file is generated in the same directory without modifying the CSV or accessing the platform or model. Task-specific analysis sections are included only when the category configuration explicitly enables a report extension.

## Optional sign-language thumbnail audit

```powershell
.\.venv\Scripts\python.exe -X utf8 -m account_filter.tasks.sign_language.cover_audit "结果CSV路径" --config configs/api.toml
```

This standalone task tool calls the explicitly selected model. It is not part of the generic classification entry point's default workflow.
