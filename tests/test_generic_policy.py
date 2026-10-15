import json
import pytest
from account_filter import __main__ as cli
from account_filter.category import load_category
from account_filter.report import generate
from task_helpers import API_PATH, API_CONFIG


def test_classification_requires_explicit_api_and_category():
    for flags in ([], ['--config', str(API_PATH)], ['--category', 'sign-language']):
        with pytest.raises(SystemExit):
            cli.parser().parse_args(['batch', 'https://www.douyin.com/user/a', *flags])


def test_collecting_does_not_require_model_or_category_configuration(tmp_path):
    for command in ('login', 'collect'):
        args = cli.parser().parse_args([command, 'https://www.douyin.com/user/a'])
        assert not hasattr(args, 'model')
    args = cli.parser().parse_args(['batch', 'https://www.douyin.com/user/a', '--refresh-cache'])
    assert args.api_config is None and args.category_spec is None
    (tmp_path / 'refresh-settings.json').write_text('{"refresh_cache":true}')
    args = cli.parser().parse_args(['batch', '--resume', str(tmp_path)])
    assert args.api_config is None and args.category_spec is None


def test_old_experiment_requires_config_but_saved_explicit_selection_can_resume(tmp_path):
    with pytest.raises(SystemExit):
        cli.parser().parse_args(['batch', '--resume', str(tmp_path)])
    task = load_category('sign-language')
    (tmp_path / 'category.json').write_text(json.dumps(task))
    (tmp_path / 'api-config.json').write_text(json.dumps(API_CONFIG))
    args = cli.parser().parse_args(['batch', '--resume', str(tmp_path)])
    assert args.category_spec == task and args.api_config == API_CONFIG


def test_old_csv_does_not_implicitly_select_a_category(tmp_path):
    path = tmp_path / 'results.csv'
    path.write_text('账户名称,频道网址,预测结果,人工标注,频道概率\nA,https://www.douyin.com/user/a,手语频道,手语频道,.9\n', encoding='utf-8-sig')
    with pytest.raises(ValueError, match='--category'):
        generate(path)
    before = path.read_bytes()
    html, summary = generate(path, category='sign-language')
    assert summary['matched'] == 1 and path.read_bytes() == before
    assert '候选数量规则的敏感性分析' in html.read_text(encoding='utf-8')


def test_generic_modules_do_not_contain_task_or_provider_defaults():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'account_filter'
    for path in root.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        assert all(word not in text for word in ('手语', 'sign_language', 'sign-language', 'openrouter', 'OpenRouter')), path.name
    text = (root / 'templates/analysis.html').read_text(encoding='utf-8')
    assert '手语' not in text and 'SIGN CHANNEL' not in text
