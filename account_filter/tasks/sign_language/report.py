"""Explicitly selected report components for this task only."""
import os
from pathlib import Path


def components():
    directory = Path(__file__).parent
    return {slot: (directory / f'report-{slot}.{"js" if slot == "scripts" else "html"}').read_text(encoding='utf-8')
            for slot in ('top', 'evidence', 'scripts', 'nav', 'style')}


def augment_payload(payload, csv_path, output):
    from ...report import read_json, relative_file
    pointer = read_json(csv_path.parent / 'cover-audit/latest.json')
    if not pointer.get('path'):
        return
    audit_path = relative_file(csv_path.parent / pointer['path'], csv_path.parent)
    audit = read_json(csv_path.parent / audit_path) if audit_path else {}
    if audit.get('source_sha256') != payload['sha256']:
        return
    if output.parent != csv_path.parent:
        for row in audit.get('rows', []):
            for video in row.get('videos', []):
                if video.get('cover'):
                    video['cover'] = Path(os.path.relpath(csv_path.parent / video['cover'], output.parent)).as_posix()
            if row.get('response'):
                row['response'] = Path(os.path.relpath(csv_path.parent / row['response'], output.parent)).as_posix()
        audit['csv'] = Path(os.path.relpath(csv_path.parent / audit['csv'], output.parent)).as_posix()
    payload['cover_audit'] = audit
