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


def test_argos_en_to_ko(monkeypatch):
    class FakeTranslate:
        @staticmethod
        def translate(text, from_code, to_code):
            return "초대"

    class FakePackage:
        @staticmethod
        def update_package_index():
            return None

        @staticmethod
        def get_installed_packages():
            return ["stub"]

        @staticmethod
        def install_from_path(path):
            return None

    class FakeSettings:
        @staticmethod
        def get_package_path():
            return "/tmp/argos"

    fake_translate = type("FakeTranslateModule", (), {"translate": FakeTranslate.translate})
    fake_package = type(
        "FakePackageModule",
        (),
        {
            "update_package_index": FakePackage.update_package_index,
            "get_installed_packages": FakePackage.get_installed_packages,
            "install_from_path": FakePackage.install_from_path,
        },
    )
    fake_settings = type("FakeSettingsModule", (), {"get_package_path": FakeSettings.get_package_path})
    fake_root = type("FakeArgosRoot", (), {})()
    fake_root.translate = fake_translate
    fake_root.package = fake_package
    fake_root.settings = fake_settings
    monkeypatch.setitem(sys.modules, "argostranslate", fake_root)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", fake_translate)
    monkeypatch.setitem(sys.modules, "argostranslate.package", fake_package)
    monkeypatch.setitem(sys.modules, "argostranslate.settings", fake_settings)
    result = translate_text("invite", preferred_provider="argos", direction="en_to_ko")
    assert result.provider_used == "argos"
    assert "초대" in result.translated


def test_argos_ko_to_en(monkeypatch):
    class FakeTranslate:
        @staticmethod
        def translate(text, from_code, to_code):
            return "hello"

    class FakePackage:
        @staticmethod
        def update_package_index():
            return None

        @staticmethod
        def get_installed_packages():
            return ["stub"]

        @staticmethod
        def install_from_path(path):
            return None

    class FakeSettings:
        @staticmethod
        def get_package_path():
            return "/tmp/argos"

    fake_translate = type("FakeTranslateModule", (), {"translate": FakeTranslate.translate})
    fake_package = type(
        "FakePackageModule",
        (),
        {
            "update_package_index": FakePackage.update_package_index,
            "get_installed_packages": FakePackage.get_installed_packages,
            "install_from_path": FakePackage.install_from_path,
        },
    )
    fake_settings = type("FakeSettingsModule", (), {"get_package_path": FakeSettings.get_package_path})
    fake_root = type("FakeArgosRoot", (), {})()
    fake_root.translate = fake_translate
    fake_root.package = fake_package
    fake_root.settings = fake_settings
    monkeypatch.setitem(sys.modules, "argostranslate", fake_root)
    monkeypatch.setitem(sys.modules, "argostranslate.translate", fake_translate)
    monkeypatch.setitem(sys.modules, "argostranslate.package", fake_package)
    monkeypatch.setitem(sys.modules, "argostranslate.settings", fake_settings)
    result = translate_text("안녕", preferred_provider="argos", direction="ko_to_en")
    assert result.provider_used == "argos"
    assert "hello" in result.translated.lower()
