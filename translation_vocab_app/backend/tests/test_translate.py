import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import json
from unittest.mock import Mock

from services.translate import translate_text  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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


def test_deepl_en_to_ko(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "test-key")
    payload = {"translations": [{"text": "사랑"}]}
    monkeypatch.setattr("services.translate.urlopen", Mock(return_value=FakeResponse(payload)))
    result = translate_text("love", preferred_provider="deepl", direction="en_to_ko")
    assert result.provider_used == "deepl"
    assert "사랑" in result.translated


def test_deepl_ko_to_en(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "test-key")
    payload = {"translations": [{"text": "love"}]}
    monkeypatch.setattr("services.translate.urlopen", Mock(return_value=FakeResponse(payload)))
    result = translate_text("사랑", preferred_provider="deepl", direction="ko_to_en")
    assert result.provider_used == "deepl"
    assert "love" in result.translated.lower()
