import pytest


@pytest.fixture(autouse=True)
def isolated_collection_cache(tmp_path, monkeypatch):
    from account_filter import cache
    monkeypatch.setattr(cache, 'DEFAULT_CACHE', tmp_path / 'data' / 'channels')
