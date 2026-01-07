import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from services.translate import translate_text  # noqa: E402


def test_hello_en_to_ko_offline():
    result = translate_text("hello", preferred_provider="offline", direction="en_to_ko")
    assert "안녕" in result.translated or "안녕하세요" in result.translated
    assert result.dest_lang == "ko"


def test_love_en_to_ko_offline():
    result = translate_text("love", preferred_provider="offline", direction="en_to_ko")
    assert "사랑" in result.translated
    assert result.dest_lang == "ko"


def test_sarang_ko_to_en_offline():
    result = translate_text("사랑", preferred_provider="offline", direction="ko_to_en")
    assert "love" in result.translated.lower()
    assert result.dest_lang == "en"
