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


def test_cli_en_to_ko(monkeypatch, tmp_path):
    cli_path = tmp_path / "translator_cli.py"
    cli_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("services.translate.CliProvider.is_ready", lambda self: True)
    monkeypatch.setattr("services.translate.CliProvider.__init__", lambda self: setattr(self, "cli_path", cli_path))

    class FakeCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = "초대"
            self.stderr = ""

    monkeypatch.setattr("services.translate.subprocess.run", lambda *args, **kwargs: FakeCompleted())
    result = translate_text("invite", preferred_provider="cli", direction="en_to_ko")
    assert result.provider_used == "cli"
    assert "초대" in result.translated


def test_cli_ko_to_en(monkeypatch, tmp_path):
    cli_path = tmp_path / "translator_cli.py"
    cli_path.write_text("", encoding="utf-8")
    monkeypatch.setattr("services.translate.CliProvider.is_ready", lambda self: True)
    monkeypatch.setattr("services.translate.CliProvider.__init__", lambda self: setattr(self, "cli_path", cli_path))

    class FakeCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = "hello"
            self.stderr = ""

    monkeypatch.setattr("services.translate.subprocess.run", lambda *args, **kwargs: FakeCompleted())
    result = translate_text("안녕", preferred_provider="cli", direction="ko_to_en")
    assert result.provider_used == "cli"
    assert "hello" in result.translated.lower()
