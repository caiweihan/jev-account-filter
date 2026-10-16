"""Attach source-matched audit data to a report, independently of its category."""
import os
from pathlib import Path


def attach_cover_audit(payload, csv_path, output):
    from .report import read_json, relative_file
    root = csv_path.parent
    pointer = read_json(root / 'cover-audit/latest.json')
    if not pointer.get('path'):
        return
    path = relative_file(root / pointer['path'], root)
    audit = read_json(root / path) if path else {}
    if audit.get('source_sha256') != payload['sha256']:
        return
    # Every local link is validated before rebasing it to the exported HTML.
    def link(value):
        checked = relative_file(root / value, root) if value else None
        return Path(os.path.relpath(root / checked, output.parent)).as_posix() if checked else None
    for row in audit.get('rows', []):
        row['response'] = link(row.get('response'))
        for video in row.get('videos', []):
            video['cover'] = link(video.get('cover'))
    audit['csv'] = link(audit.get('csv'))
    payload['cover_audit'] = audit
