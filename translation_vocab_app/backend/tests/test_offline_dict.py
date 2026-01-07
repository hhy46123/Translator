import importlib
import json
import zipfile


def _write_sample_zip(zip_path):
    payload = {
        "LexicalResource": {
            "Lexicon": {
                "LexicalEntry": [
                    {
                        "Lemma": {"feat": [{"att": "writtenForm", "val": "가장자리"}]},
                        "Sense": [
                            {
                                "feat": [{"att": "definition", "val": "사물의 끝부분"}],
                                "Equivalent": [
                                    {
                                        "feat": [
                                            {"att": "language", "val": "영어"},
                                            {"att": "lemma", "val": "edge"},
                                        ]
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "Lemma": {"feat": [{"att": "writtenForm", "val": "표면"}]},
                        "Sense": [
                            {
                                "feat": [{"att": "definition", "val": "겉의 부분"}],
                                "Equivalent": [
                                    {
                                        "feat": [
                                            {"att": "language", "val": "영어"},
                                            {"att": "lemma", "val": "surface"},
                                        ]
                                    }
                                ],
                            }
                        ],
                    },
                ]
            }
        }
    }
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("1_5000_20251219.json", json.dumps(payload, ensure_ascii=False))


def test_offline_lookup_ko_and_en(tmp_path, monkeypatch):
    zip_path = tmp_path / "korean_dict.zip"
    _write_sample_zip(zip_path)
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("OFFLINE_DICT_ZIP_PATH", str(zip_path))
    monkeypatch.setenv("OFFLINE_DICT_CACHE_DIR", str(cache_dir))

    offline_dict = importlib.import_module("offline_dict")
    importlib.reload(offline_dict)

    ko_results = offline_dict.lookup_ko("가장자리")
    assert ko_results
    assert "edge" in ko_results[0]["en"]

    en_results = offline_dict.lookup_en("edge")
    assert en_results
    assert en_results[0]["ko"] == "가장자리"
