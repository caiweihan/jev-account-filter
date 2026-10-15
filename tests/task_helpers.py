"""Explicit fixtures for regression cases belonging to the existing example task."""
from pathlib import Path
from account_filter import classifier, report
from account_filter.category import load_category, category_labels
from account_filter.config import load_config

PROJECT = Path(__file__).resolve().parents[1]
API_PATH = PROJECT / 'configs/api.toml'
TASK = load_category('sign-language')
API_CONFIG = load_config(API_PATH)


def parse_task_args(cli, args):
    args = list(args)
    if args[0] in ('run', 'analyze', 'batch'):
        if '--config' not in args:
            args.extend(['--config', str(API_PATH)])
        if '--category' not in args:
            args.extend(['--category', 'sign-language'])
    return cli.parser().parse_args(args)


def build_request(*args, **kwargs):
    return classifier.build_request(*args, **{'api': 'decisions', 'category': TASK,
        'max_videos': 12, 'image_side': API_CONFIG['image_side'], 'context_budget': API_CONFIG['context_budget'],
        'image_tokens': API_CONFIG['image_token_estimate'], **kwargs})


def build_title_request(*args, **kwargs):
    return classifier.build_title_request(*args, **{'api': 'decisions', 'category': TASK,
        'context_budget': API_CONFIG['context_budget'], **kwargs})


def normalize_result(*args, **kwargs):
    return classifier.normalize_result(*args, category=TASK, **kwargs)


def summarize(rows):
    return report.summarize(rows, category_labels(TASK))
