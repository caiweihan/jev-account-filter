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
| `conftest.py` | Isolating test caches in temporary directories |

```powershell
uv pip install --cache-dir .cache/uv --python .venv/Scripts/python.exe pytest
.\.venv\Scripts\python.exe -X utf8 -m pytest tests --basetemp=.cache/pytest-check -q
```

`pytest` is a development dependency and is not needed for everyday experiments. Generated files such as `.cache/pytest-*` and `__pycache__` can be deleted; keep the test `.py` sources.

## Entry points and existing data

Commands and tests consistently use `account_filter`; Douyin parsing is imported from `account_filter.platforms.douyin`. The API client uses `call_model_api`, with protocol, endpoint, and credential-variable name explicitly supplied to every call. CSV columns and collection caches remain unchanged. New inference results use the generic field `relevance_probability`; historical files are not rewritten.

The generic report loads task-specific components through `report_extension` in the category configuration, without guessing the task from labels or CSV content. When changing a category or model, use a new experiment output directory and preserve historical results and configuration snapshots for comparison.
