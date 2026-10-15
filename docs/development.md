[English](development.md) | [简体中文](development.zh-CN.md)

# Developer guide: extension and testing

This guide is for developers adding platforms, extending categories, or modifying code. To run existing tasks, see [Commands](commands.md); for category and API settings, see [Configuration](configuration.md).

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `__main__.py` | Input, batches, progress, and resuming |
| `category.py` / `classifier.py` | Category configuration, two-pass requests, and answer validation |
| `api.py` | Provider-neutral HTTP client and protocol parsing |
| `platforms/douyin.py` / `platforms/kuaishou.py` | Platform fields, post types, and page extraction |
| `platforms/registry.py` | Routing to implemented platforms |
| `collector.py` | Shared browser, login, collection orchestration, state handling, and thumbnail archiving |
| `cache.py` / `report.py` | Canonical cache and offline reports |
| `tasks/sign_language/cover_audit.py` | Standalone thumbnail-feature checks for the sign-language task |

Paths in the table are relative to `account_filter/`. Platform parsers are stored separately; the shared collector manages browser sessions and collection orchestration. Adding a platform requires connecting its parser, routing, and shared collection workflow.

## Adding a platform

1. Implement profile-page, target-creator metadata, and first-page post parsing under `account_filter/platforms/`.
2. Return `platform/url/name/bio/videos`; each work includes `id/title/url/cover_url`. Preserve type evidence and provenance.
3. Handle login, empty accounts, and risk-control states; do not mistake recommendations for the creator's own works.
4. Update routing, the CLI, and input platform mappings, reusing the cache and classification pipeline.
5. Use saved responses and local pages to verify creator identity, post types, collection scope, and resume behavior.

To extend categories, copy a category TOML rather than embedding category judgments in platform adapters. The current workflow treats a lack of public videos as negative, so it suits categories that rely on video evidence.

## Local validation

`tests/` uses local fixtures and mocked responses to verify collection, classification, caching, and resuming without visiting real platforms or calling paid models. Run relevant tests after modifying a module, and the full suite when changing shared workflows or refactoring.

| File | Behavior protected |
| --- | --- |
| `test_pipeline.py` / `test_two_stage.py` | Creator filtering, complete first-page titles, title-first selection, thumbnail alignment, and answer validation |
| `test_post_types.py` | Excluding image/article posts and recovering post-type evidence |
| `test_batch.py` / `test_resume.py` / `test_reclassify.py` | CSV handling, skipping successful entries, retrying failures, and offline mode |
| `test_user_not_found.py` | Distinguishing nonexistent users from ordinary errors |
| `test_cover_formats.py` | HEIC and other thumbnail formats |
| `test_config.py` / `test_categories.py` | API and category configuration |
| `test_report.py` / `test_cover_audit.py` | Reports, thumbnail audits, missing values, and local-file boundaries |
| `test_viewer.py` | Browser CSV loading, external thumbnail alignment, category restoration, reloads, and text escaping |
| `test_second_review.py` | Dataset composition, reannotation matching, fixed denominators, conflicts, and review filters |
| `conftest.py` | Isolating test caches in temporary directories |

```powershell
uv pip install --cache-dir .cache/uv --python .venv/Scripts/python.exe pytest
.\.venv\Scripts\python.exe -X utf8 -m pytest tests --basetemp=.cache/pytest-check -q
```

`pytest` is a development dependency and is not needed for everyday experiments. Generated files such as `.cache/pytest-*` and `__pycache__` can be deleted; keep the test `.py` sources.

## Entry points and existing data

Commands and tests consistently use `account_filter`; Douyin parsing is imported from `account_filter.platforms.douyin`. The API client uses `call_model_api`, with protocol, endpoint, and credential-variable name explicitly supplied to every call. CSV columns and collection caches remain unchanged. New inference results use the generic field `relevance_probability`; historical files are not rewritten.

The generic report loads task-specific components through `report_extension` in the category configuration, without guessing the task from labels or CSV content. When changing a category or model, use a new experiment output directory and preserve historical results and configuration snapshots for comparison.

## Browser analysis page

The root `analysis.html` is an offline viewer containing no experiment data. `account_filter/viewer.py` bundles the existing generic report and explicitly configured task extensions; the outer UI and loading logic live in `templates/viewer.html` and `templates/viewer.js`. Charts and task simulations reuse the existing components. CSV parsing and summaries run in the browser, with tests comparing summaries against the Python implementation.

After editing report components, viewer sources, or category configurations, run `python -m account_filter.viewer` to update the root HTML. Switching CSVs does not require rebuilding. Caches are read through user-selected `File` objects; only displayed candidate assets are transferred to the isolated report, which creates its own Blob URLs without downloading remote images. Match channels and videos by URL when adding cache formats, rather than relying on CSV row numbers or directory order.

`templates/analysis-extra.js` provides shared label/review helpers; `analysis-evaluation.js` derives reference-specific rows for unified performance, distributions, error profiles, and account details. Original `D.rows` fields remain unchanged. `analysis-cluster.js` uses deterministic farthest-point K-means initialization on five complete scores plus prediction one-hot features; human labels are excluded. PCA only projects the full feature space for display. Empty/duplicate feature sets and missing scores have explicit handling. `test_dashboard.py` checks clustering determinism, prediction-category effects, annotation leakage, cohort denominators, error filters, automatic settings, and page scrolling.

The reference selector distinguishes original-label agreement, reviewed-cohort accuracy, and full-dataset conditional estimates. Both human and model metrics use the same valid cohort. Estimates retaining unreviewed original labels are explicitly conditional, never described as independent full-dataset validation. `viewer.js` still matches reviews by unique identity and retains conflicts under `second_review`. Static reports reuse the analysis components but do not automatically load another CSV.

The sandboxed report posts measured body height to the parent using a per-render token and verified window source, allowing a single outer scroll without removing isolation. Browser-viewer evidence opens inline, while standalone exported reports retain their native dialogs. Category inference matches configured labels or an exact experiment snapshot, without guessing a positive label for unknown categories. Automatic encoding uses strict UTF-8/GB18030 decoding and UTF-16 BOM detection; ambiguous categories and overrides remain in collapsed settings. Selected filenames and folder names use text nodes rather than native input state.

`templates/viewer-session.js` persists read-only file/directory handles, UI choices, and the last analysis in IndexedDB, scoped to the HTML path. The snapshot contains input data and only referenced candidate/audit assets, with compacted asset IDs. Opening the page restores this snapshot without a click and queries disk permissions without prompting; a manual update alone may request read access. Available handles reread latest files; cached evidence is matched by channel/video URL when disk access is unavailable. Snapshot timestamps distinguish cached results from fresh data. Clearing choices removes both handles and the snapshot; storage failures preserve the current analysis. `test_viewer_session.py` checks fictional snapshots, decoded cached thumbnails, permission expiry, file changes, clearing, and storage fallback. Keep the isolated report sandbox and offline CSP intact.

`file://` uses regular file inputs and snapshot restoration without rereading old native handles. Native mode catches denied picker and `getFile()` calls, including `NotAllowedError` and `SecurityError`, and reveals regular selection instead of trusting `queryPermission()` alone. Directory enumeration requests only JSON, CSV, and images; every file-read Promise immediately catches rejections, skips unreadable entries, and reports missing data. Tests cover granted permission queries followed by denied reads, old-handle migration, and restricted directory entries.
