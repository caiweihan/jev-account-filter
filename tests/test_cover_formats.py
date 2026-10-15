import asyncio
import io
from types import SimpleNamespace

import pytest
from PIL import Image
from pillow_heif import register_heif_opener

from account_filter.collector import download_cover


@pytest.mark.parametrize('format', ['JPEG', 'HEIF'])
def test_cdn_jpeg_url_can_return_heic_and_cache_is_jpeg(tmp_path, format):
    register_heif_opener()
    content = io.BytesIO()
    Image.new('RGB', (16, 24), 'green').save(content, format=format)
    class Response:
        ok = True
        async def body(self): return content.getvalue()
    class Request:
        async def get(self, url, **kwargs):
            assert url.endswith('.jpeg')
            return Response()
    path = tmp_path / 'covers/1.jpg'
    asyncio.run(download_cover(SimpleNamespace(request=Request()), 'https://p3.douyinpic.com/cover.jpeg', path))
    with Image.open(path) as image:
        image.load()
        assert image.format == 'JPEG' and image.size == (16, 24) and image.mode == 'RGB'
