"""URL routing metadata for implemented collectors; no speculative adapters."""
import tomllib
from pathlib import Path

with (Path(__file__).resolve().parents[2] / 'configs/platforms.toml').open('rb') as stream:
    PLATFORMS = tomllib.load(stream)

if set(PLATFORMS) - {'kuaishou', 'douyin'}:
    raise ValueError('平台配置包含尚未实现的适配器；请先实现采集逻辑再启用。')
