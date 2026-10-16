[English](data-format.md) | [简体中文](data-format.zh-CN.md)

# Dataset format (version 1)

The dataset is the formal boundary between collection and screening. Custom sources need no crawler changes, platform registration, or network API: provide these files and screen them with the existing pipeline. The model consumes metadata, titles, and static thumbnails.

```text
my-dataset/
├── dataset.json
├── manifest.csv
└── channels/
    └── example/
        ├── channel.json
        └── covers/1.jpg
```

`dataset.json`:

```json
{"schema_version": 1, "manifest": "manifest.csv"}
```

`manifest.csv` (UTF-8):

```csv
platform,account_id,url,name,annotation,path,status,error
custom,example,https://example.org/account,Example,,channels/example/channel.json,ready,
```

`channel.json`:

```json
{
  "platform": "custom",
  "id": "example",
  "url": "https://example.org/account",
  "name": "Example",
  "bio": "Account biography",
  "scope": "All videos on the collected first page",
  "videos": [
    {
      "id": "1",
      "title": "Video title",
      "url": "https://example.org/video/1",
      "content_type": "video",
      "cover_path": "covers/1.jpg"
    }
  ]
}
```

## Field contract

- One manifest row per account; all headers are required. `platform + account_id` is unique and must match JSON `platform + id`. URLs must match too. Custom sources may use any nonempty platform name, such as `custom`.
- `path` is relative to the dataset root; `cover_path` is relative to the account JSON directory. Both must stay inside those directories. Remote images and escaping paths are rejected. The dataset remains portable as a whole.
- `annotation` may be blank. It is used only for result comparisons and never sent to the model. Keep empty columns rather than removing headers.
- Status: `ready` can be screened; `private` and `user_not_found` mark unavailable accounts; `pending` and `failed` mark incomplete collection, recorded as screening errors.
- Account JSON requires `platform/id/url/name/bio/videos`. Text fields are strings. `videos` is an array with unique nonempty video IDs and string `title/url` fields. Titles and biographies may be empty.
- Only verified videos belong in `videos`. Image posts/articles may be preserved separately in `excluded_posts`. Use an empty video list and `no_posts: true` for accounts without posts, or `no_video_posts: true` for non-video-only accounts. Empty candidates are classified negative without a model call under the current policy.
- `cover_path` is optional. Missing images yield title-only evidence and a warning, never an automatic download. JPEG/PNG/WebP static images are recommended; full videos are unnecessary.
- `scope` should document collection time, first-page scope, or a selected subset. Preserve additional provenance and type evidence if useful; screening does not interpret private platform fields.

```powershell
.\.venv\Scripts\python.exe -m account_filter validate-data data/my-dataset
```

Screening never modifies the dataset. Results, rule snapshots, and model responses go to a separate `results/<experiment>/` directory. A real working example is available in [`examples/real-demo/data`](../examples/real-demo/data).

## Built-in collection and extension

The Douyin and Kuaishou collectors produce this format directly. Platform implementations live in `account_filter/collection/platforms/`; model screening and API logic live separately in `account_filter/screening/`. Add a same-named adapter module and a `configs/platforms.toml` entry for a new collection platform. Custom data sources only need data files and are not restricted by the built-in platform list.
