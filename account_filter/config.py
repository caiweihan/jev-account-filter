"""Explicit model-service configuration; secrets are read only from environment."""
import argparse
import json
import tomllib
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_FIELDS = ('model', 'api', 'endpoint', 'api_key_env')
RUNTIME_DEFAULTS = {'timeout_seconds': 120, 'context_budget': 60000,
                    'image_side': 512, 'image_token_estimate': 1536}


def validate_config(values):
    unknown = values.keys() - {*REQUIRED_FIELDS, *RUNTIME_DEFAULTS}
    if unknown:
        raise ValueError(f'API 配置中有未知字段：{", ".join(sorted(unknown))}')
    config = {**RUNTIME_DEFAULTS, **values}
    for key in REQUIRED_FIELDS:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'API 配置必须明确填写 {key}，不能留空。')
    if config['api'] not in ('decisions', 'chat'):
        raise ValueError('API 配置 api 仅支持 decisions 或 chat。')
    endpoint = urlparse(config['endpoint'])
    local_http = endpoint.scheme == 'http' and endpoint.hostname in ('localhost', '127.0.0.1', '::1')
    if (endpoint.scheme != 'https' and not local_http) or not endpoint.hostname or endpoint.username or endpoint.password:
        raise ValueError('API 配置 endpoint 必须是 HTTPS 地址（本机回环地址可用 HTTP），不能包含用户名或密码。')
    for key in ('context_budget', 'image_side', 'image_token_estimate'):
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError(f'API 配置 {key} 必须是正整数。')
    if not 64 <= config['image_side'] <= 2048:
        raise ValueError('API 配置 image_side 必须在 64..2048 之间。')
    if type(config['timeout_seconds']) not in (int, float) or not 0 < config['timeout_seconds'] <= 3600:
        raise ValueError('API 配置 timeout_seconds 必须在 (0, 3600] 内。')
    return config


def load_config(path):
    try:
        with Path(path).open('rb') as stream:
            return validate_config(tomllib.load(stream))
    except (OSError, ValueError) as exc:
        raise ValueError(f'无法读取 API 配置 {path}：{exc}') from exc


def saved_config(directory):
    path = Path(directory) / 'api-config.json'
    return validate_config(json.loads(path.read_text(encoding='utf-8'))) if path.is_file() else None


class ConfigArgumentParser(argparse.ArgumentParser):
    def parse_args(self, args=None, namespace=None):
        result = super().parse_args(args, namespace)
        if not hasattr(result, 'config'):
            return result
        from .category import load_category, saved_category
        resume = getattr(result, 'resume', None)
        cache_only = bool(getattr(result, 'refresh_cache', False) or getattr(result, 'backfill_only', False)
                          or (resume and (resume / 'refresh-settings.json').is_file()))
        try:
            config = load_config(result.config) if result.config else (saved_config(resume) if resume else None)
            task = load_category(result.category) if result.category else (saved_category(resume) if resume else None)
            if not cache_only and (config is None or task is None):
                missing = '、'.join(flag for flag, value in (('--config', config), ('--category', task)) if value is None)
                raise ValueError(f'分类任务必须明确指定 {missing}；旧实验缺少配置快照时也需显式提供。')
            result.category_spec = task
            result.api_config = config
            if config:
                for key, value in config.items():
                    setattr(result, key, value)
        except (OSError, ValueError) as exc:
            self.error(str(exc))
        return result
