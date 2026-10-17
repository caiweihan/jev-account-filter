import base64
import io

import pytest
from PIL import Image

from account_filter.screening.classifier import encode_cover


@pytest.mark.parametrize('size,side,expected', [
    ((276, 368), 512, (280, 368)),
    ((256, 256), 512, (280, 280)),
    ((40, 90), 512, (280, 280)),
    ((2000, 100), 512, (512, 280)),
    ((100, 2000), 512, (280, 512)),
    ((2000, 2000), 2048, (1568, 1568)),
    ((323, 430), 512, (323, 430)),
    ((323, 430), 64, (280, 280)),
])
@pytest.mark.parametrize('model', ['typesafe/jev-1.14', '~typesafe/jev-latest'])
def test_jev_encoded_image_respects_provider_limits(tmp_path, size, side, expected, model):
    path = tmp_path / 'cover.png'
    Image.new('RGB', size, 'red').save(path)
    original = path.read_bytes()
    encoded = encode_cover(path, side, model=model)
    with Image.open(io.BytesIO(base64.b64decode(encoded.split(',', 1)[1]))) as image:
        assert image.format == 'JPEG'
        assert image.size == expected
        assert 280 <= image.width <= 1568 and 280 <= image.height <= 1568
        assert 78400 <= image.width * image.height <= 2458624
        assert image.getpixel((image.width // 2, image.height // 2))[0] > 240
    assert path.read_bytes() == original


def test_other_models_keep_original_encoding(tmp_path):
    path = tmp_path / 'cover.png'
    Image.new('RGB', (276, 368), 'red').save(path)
    assert encode_cover(path, 512, model='openai/gpt-6-luna-decisions') == encode_cover(path, 512)
    assert encode_cover(path, 512, model='typesafe/jev-1.14') != encode_cover(path, 512)


def test_jev_does_not_change_already_valid_covers(tmp_path):
    path = tmp_path / 'cover.png'
    Image.new('RGB', (323, 430), 'red').save(path)
    assert encode_cover(path, 512, model='typesafe/jev-1.14') == encode_cover(path, 512)
