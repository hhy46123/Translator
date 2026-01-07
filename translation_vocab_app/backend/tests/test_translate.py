import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import json
import sys
from types import ModuleType
from unittest.mock import Mock

from services.translate import translate_text  # noqa: E402


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_hello_en_to_ko_placeholder():
    result = translate_text("hello", preferred_provider="offline_placeholder", direction="en_to_ko")
    assert "Offline translation unavailable" in result.translated
    assert result.dest_lang == "ko"


def test_love_en_to_ko_placeholder():
    result = translate_text("love", preferred_provider="offline_placeholder", direction="en_to_ko")
    assert "Offline translation unavailable" in result.translated
    assert result.dest_lang == "ko"


def test_sarang_ko_to_en_placeholder():
    result = translate_text("사랑", preferred_provider="offline_placeholder", direction="ko_to_en")
    assert "Offline translation unavailable" in result.translated
    assert result.dest_lang == "en"


def test_deepl_en_to_ko(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "test-key")
    payload = {"translations": [{"text": "사랑"}]}
    monkeypatch.setattr("services.translate.requests.post", Mock(return_value=FakeResponse(payload)))
    result = translate_text("love", preferred_provider="deepl", direction="en_to_ko")
    assert result.provider_used == "deepl"
    assert "사랑" in result.translated


def test_deepl_ko_to_en(monkeypatch):
    monkeypatch.setenv("DEEPL_API_KEY", "test-key")
    payload = {"translations": [{"text": "love"}]}
    monkeypatch.setattr("services.translate.requests.post", Mock(return_value=FakeResponse(payload)))
    result = translate_text("사랑", preferred_provider="deepl", direction="ko_to_en")
    assert result.provider_used == "deepl"
    assert "love" in result.translated.lower()


def test_argos_en_to_ko_mocked(monkeypatch):
    fake_module = ModuleType("argostranslate.translate")
    fake_module.translate = lambda text, from_code, to_code: "초대"
    sys.modules["argostranslate.translate"] = fake_module
    result = translate_text("invite", preferred_provider="argos", direction="en_to_ko")
    assert "초대" in result.translated
    assert result.provider_used == "argos"


def test_argos_ko_to_en_mocked(monkeypatch):
    fake_module = ModuleType("argostranslate.translate")
    fake_module.translate = lambda text, from_code, to_code: "hello"
    sys.modules["argostranslate.translate"] = fake_module
    result = translate_text("안녕", preferred_provider="argos", direction="ko_to_en")
    assert "hello" in result.translated.lower()
    assert result.provider_used == "argos"
