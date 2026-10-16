"""URL routing metadata for implemented collectors; no speculative adapters."""
import tomllib
import importlib
import re
from pathlib import Path

with (Path(__file__).resolve().parents[3] / 'configs/platforms.toml').open('rb') as stream:
    PLATFORMS = tomllib.load(stream)

def adapter(platform):
    """One configured platform maps to one module under this package."""
    if platform not in PLATFORMS or not re.fullmatch(r'[a-z][a-z0-9_]*', platform):
        raise ValueError(f'未配置的采集平台：{platform}')
    return importlib.import_module(f'{__package__}.{platform}')
