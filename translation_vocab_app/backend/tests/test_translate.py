import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from services.translate import translate_text  # noqa: E402


def test_localdict_en_to_ko():
    result = translate_text("invite", preferred_provider="localdict", direction="en_to_ko")
    assert result.provider_used == "localdict"
    assert result.dest_lang == "ko"
    assert "초대" in result.translated


def test_localdict_ko_to_en():
    result = translate_text("안녕", preferred_provider="localdict", direction="ko_to_en")
    assert result.provider_used == "localdict"
    assert result.dest_lang == "en"
    assert "hi" in result.translated.lower()


def test_localdict_grammar():
    result = translate_text("I am happy", preferred_provider="localdict", direction="en_to_ko")
    assert "나는" in result.translated
