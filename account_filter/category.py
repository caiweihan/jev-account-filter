"""Load category rules independently of platform collection and API settings."""
import json
import tomllib
from pathlib import Path

CONFIGS = Path(__file__).resolve().parents[1] / 'configs'
FIELDS = ('id', 'name', 'version', 'positive_label', 'negative_label', 'title_rules', 'rules',
          'channel_instructions', 'channel_yes', 'channel_no', 'channel_probability_instructions',
          'video_instructions', 'video_true', 'video_false', 'title_video_instructions',
          'best_video_instructions', 'candidate_criterion', 'none_criterion', 'analysis_warning')


def validate_category(values):
    if not isinstance(values, dict):
        raise ValueError('必须明确提供分类配置对象。')
    for field in FIELDS:
        if not isinstance(values.get(field), str) or not values[field].strip():
            raise ValueError(f'分类配置 {field} 必须是非空字符串。')
    if values['positive_label'] == values['negative_label'] or '疑难' in (values['positive_label'], values['negative_label']):
        raise ValueError('分类配置的正负标签必须不同，且不能使用保留的人工标签“疑难”。')
    for field in ('video_instructions', 'title_video_instructions', 'candidate_criterion'):
        try:
            values[field].format(key='v001')
        except (KeyError, ValueError) as exc:
            raise ValueError(f'分类配置 {field} 只支持 {{key}} 占位符。') from exc
    category = {field: values[field] for field in FIELDS}
    return category


def load_category(value):
    if not value:
        raise ValueError('必须明确指定分类配置。')
    path = Path(value)
    if not path.suffix and len(path.parts) == 1:
        path = CONFIGS / 'categories' / (str(value) + '.toml')
    try:
        with path.open('rb') as stream:
            return validate_category(tomllib.load(stream))
    except (OSError, ValueError) as exc:
        raise ValueError(f'无法读取分类配置 {path}：{exc}') from exc


def saved_category(directory):
    path = Path(directory) / 'category.json'
    return validate_category(json.loads(path.read_text(encoding='utf-8'))) if path.is_file() else None


def resolve_category(directory, value=None):
    category = validate_category(value) if isinstance(value, dict) else load_category(value) if value else saved_category(directory)
    if category is None:
        raise ValueError('实验中没有 category.json；请用 --category 明确指定分类配置。')
    return category


def category_labels(category):
    return [category['positive_label'], '疑难', category['negative_label']]
