from __future__ import annotations

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import json
import os
from pathlib import Path


def _contains_korean(text: str) -> bool:
    return bool(re.search("[\uac00-\ud7af]", text))


def detect_direction(text: str, direction: str = "auto") -> tuple[str, str]:
    """Determine src/dest based on requested direction or content."""
    if direction == "en_to_ko":
        return "en", "ko"
    if direction == "ko_to_en":
        return "ko", "en"
    # auto
    if _contains_korean(text):
        return "ko", "en"
    return "en", "ko"


@dataclass
class ProviderOutput:
    translated: str
    provider_name: str
    raw_info: Optional[dict] = None


@dataclass
class TranslationResult:
    src_lang: str
    dest_lang: str
    original: str
    translated: str
    ipa: str
    related: Dict[str, List[str]]
    provider_used: str
    error_chain: List[str]
    latency_ms: float
    raw_info: Optional[dict] = None


class TranslationProvider:
    name: str = "base"

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        raise NotImplementedError

    def health_check(self) -> Tuple[bool, str]:
        try:
            self.translate("hello", "en", "ko", timeout=3)
            return True, "ok"
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)


class LocalDictProvider(TranslationProvider):
    name = "localdict"

    def __init__(self) -> None:
        base_dir = Path(__file__).resolve().parent / "dictionaries"
        self.en_ko_path = base_dir / "en_ko.json"
        self.ko_en_path = base_dir / "ko_en.json"
        self._en_ko_cache: dict[str, str] | None = None
        self._ko_en_cache: dict[str, str] | None = None
        self._en_ko_mtime: float | None = None
        self._ko_en_mtime: float | None = None
        self._builtins = load_builtin_dictionaries()

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        en_ko, ko_en = self._load_dictionaries()
        if src_lang == "en" and dest_lang == "ko":
            translated, hits, misses = translate_en_to_ko(text, en_ko)
        else:
            translated, hits, misses = translate_ko_to_en(text, ko_en)
        if not translated:
            raise RuntimeError("empty translation from localdict")
        return ProviderOutput(
            translated=translated,
            provider_name=self.name,
            raw_info={"hits": hits, "misses": misses},
        )

    def _load_dictionaries(self) -> tuple[dict[str, str], dict[str, str]]:
        en_ko = self._load_dict(self.en_ko_path, self._builtins["en_ko"], "en_ko")
        ko_en = self._load_dict(self.ko_en_path, self._builtins["ko_en"], "ko_en")
        return en_ko, ko_en

    def _load_dict(self, path: Path, fallback: dict[str, str], which: str) -> dict[str, str]:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return fallback

        if which == "en_ko" and self._en_ko_cache is not None and self._en_ko_mtime == mtime:
            return self._en_ko_cache
        if which == "ko_en" and self._ko_en_cache is not None and self._ko_en_mtime == mtime:
            return self._ko_en_cache

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle) or {}
        if not isinstance(data, dict) or not data:
            data = fallback

        if which == "en_ko":
            self._en_ko_cache = data
            self._en_ko_mtime = mtime
        else:
            self._ko_en_cache = data
            self._ko_en_mtime = mtime
        return data


class PlaceholderProvider(TranslationProvider):
    name = "offline_placeholder"

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        message = "Offline translation unavailable. Update dictionary files for local translations."
        return ProviderOutput(translated=message, provider_name=self.name, raw_info={"offline": True})


def generate_related(text: str, src_lang: str, dest_lang: str) -> Dict[str, List[str]]:
    base = text.split()
    root = base[0] if base else text
    samples = [f"{root}-{i}" for i in range(1, 3)]
    phrases = [
        f"{root} in context",
        f"{root} for beginners",
    ]
    examples = [
        f"{root} example sentence {random.randint(1,99)}.",
        f"Using {root} when speaking {dest_lang.upper()}.",
    ]
    if dest_lang == "ko":
        noun_forms = [f"{root} thing", f"{root} item"]
        verb_forms = [f"to {root}", f"{root}ing"]
        adj_forms = [f"{root}-like", f"{root} style"]
    else:
        noun_forms = [f"{root} (명사)", f"{root} (대상)"]
        verb_forms = [f"{root}하다", f"{root}되다"]
        adj_forms = [f"{root}스러운", f"{root}적인"]

    return {
        "noun_forms": noun_forms + samples[:1],
        "verb_forms": verb_forms,
        "adj_forms": adj_forms,
        "phrases": phrases,
        "examples": examples,
    }


def generate_ipa(text: str, lang: str) -> str:
    if not text:
        return ""
    if lang.startswith("ko"):
        spaced = " ".join(list(text))
        return f"[ko] /{spaced}/"
    phonetic = " ".join([syllable.lower() for syllable in re.findall(r"[a-zA-Z']+", text) or [text]])
    return f"[en] /{phonetic}/"


def translate_text(text: str, preferred_provider: Optional[str] = "auto", direction: str = "auto") -> TranslationResult:
    return translate_text_with_direction(text=text, preferred_provider=preferred_provider, direction=direction)


def translate_text_with_direction(
    text: str, preferred_provider: Optional[str] = "auto", direction: str = "auto"
) -> TranslationResult:
    src_lang, dest_lang = detect_direction(text, direction)

    local_provider = LocalDictProvider()
    placeholder_provider = PlaceholderProvider()

    providers = {
        "localdict": local_provider,
        "offline_placeholder": placeholder_provider,
    }
    order = ["localdict", "offline_placeholder"]
    if preferred_provider and preferred_provider != "auto" and preferred_provider in providers:
        order = [preferred_provider] + [p for p in order if p != preferred_provider]

    error_chain: List[str] = []
    chosen: Optional[ProviderOutput] = None
    latency_ms: float = 0.0

    for name in order:
        provider = providers[name]
        for attempt in range(2):
            start = time.perf_counter()
            try:
                output = provider.translate(text, src_lang, dest_lang, timeout=5)
                if output.translated:
                    chosen = output
                    latency_ms = (time.perf_counter() - start) * 1000
                    break
            except Exception as exc:  # pragma: no cover - defensive
                error_chain.append(f"{provider.name} attempt {attempt+1}: {exc}")
                continue
        if chosen:
            break

    if not chosen:
        chosen = ProviderOutput(
            translated="Offline translation unavailable. Update dictionary files for local translations.",
            provider_name="offline_placeholder",
            raw_info={"fallback": True},
        )

    ipa_text = generate_ipa(text, src_lang)
    related = generate_related(text, src_lang, dest_lang)

    if chosen.provider_name == "localdict" and isinstance(chosen.raw_info, dict):
        error_chain.append("localdict used")
        error_chain.append(f"hits: {chosen.raw_info.get('hits', 0)}, misses: {chosen.raw_info.get('misses', 0)}")

    return TranslationResult(
        src_lang=src_lang,
        dest_lang=dest_lang,
        original=text,
        translated=chosen.translated,
        ipa=ipa_text,
        related=related,
        provider_used=chosen.provider_name,
        error_chain=error_chain,
        latency_ms=round(latency_ms, 2),
        raw_info=chosen.raw_info,
    )


def run_with_timeout(func, timeout: int = 5):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        return future.result(timeout=timeout)


def providers_health():
    providers = [LocalDictProvider(), PlaceholderProvider()]
    status = {}
    for provider in providers:
        ok, message = provider.health_check()
        status[provider.name] = {"ok": ok, "message": message}
    return status


def load_builtin_dictionaries() -> dict[str, dict[str, str]]:
    en_words = [
        "hello","hi","goodbye","please","thanks","sorry","yes","no","today","tomorrow","yesterday",
        "love","invite","string","cat","dog","eat","go","make","do","be","have","good","bad","new","old",
        "man","woman","child","friend","family","home","house","school","work","study","book","water","food",
        "coffee","tea","milk","apple","banana","orange","rice","bread","meat","fish","time","day","week",
        "month","year","morning","night","happy","sad","fast","slow","big","small","hot","cold","city","country",
    ]
    en_ko = {word: word for word in en_words}
    en_ko.update(
        {
            "hello": "안녕하세요",
            "hi": "안녕",
            "goodbye": "안녕히 가세요",
            "please": "제발",
            "thanks": "감사합니다",
            "sorry": "미안합니다",
            "yes": "네",
            "no": "아니요",
            "today": "오늘",
            "tomorrow": "내일",
            "yesterday": "어제",
            "love": "사랑",
            "invite": "초대",
            "string": "문자열",
            "cat": "고양이",
            "dog": "개",
            "eat": "먹다",
            "go": "가다",
            "make": "만들다",
            "do": "하다",
            "be": "이다",
            "have": "가지다",
            "good": "좋다",
            "bad": "나쁘다",
            "new": "새로운",
            "old": "오래된",
            "man": "남자",
            "woman": "여자",
            "child": "아이",
            "friend": "친구",
            "family": "가족",
            "home": "집",
            "house": "집",
            "school": "학교",
            "work": "일",
            "study": "공부하다",
            "book": "책",
            "water": "물",
            "food": "음식",
            "coffee": "커피",
            "tea": "차",
            "milk": "우유",
            "apple": "사과",
            "banana": "바나나",
            "orange": "오렌지",
            "rice": "쌀",
            "bread": "빵",
            "meat": "고기",
            "fish": "생선",
            "time": "시간",
            "day": "날",
            "week": "주",
            "month": "달",
            "year": "년",
            "morning": "아침",
            "night": "밤",
            "happy": "행복한",
            "sad": "슬픈",
            "fast": "빠른",
            "slow": "느린",
            "big": "큰",
            "small": "작은",
            "hot": "뜨거운",
            "cold": "차가운",
            "city": "도시",
            "country": "나라",
        }
    )
    ko_en = {value: key for key, value in en_ko.items()}
    return {"en_ko": en_ko, "ko_en": ko_en}


def translate_en_to_ko(text: str, dictionary: dict[str, str]) -> tuple[str, int, int]:
    tokens = tokenize(text)
    hits = 0
    misses = 0
    output = []
    for token, token_type in tokens:
        if token_type != "word":
            output.append(token)
            continue
        lowered = token.lower()
        translated = None
        if lowered in {"i", "you"}:
            translated = dictionary.get(lowered)
        if translated is None and lowered.endswith("s") and len(lowered) > 3:
            translated = dictionary.get(lowered[:-1])
        if translated is None:
            translated = dictionary.get(lowered)
        if translated:
            hits += 1
            output.append(translated)
        else:
            misses += 1
            output.append(token)
    rendered = "".join(output)
    rendered = apply_en_to_ko_grammar(rendered)
    return rendered, hits, misses


def translate_ko_to_en(text: str, dictionary: dict[str, str]) -> tuple[str, int, int]:
    tokens = tokenize(text)
    hits = 0
    misses = 0
    output = []
    for token, token_type in tokens:
        if token_type != "word":
            output.append(token)
            continue
        stripped = strip_korean_particles(token)
        stripped = strip_korean_endings(stripped)
        translated = dictionary.get(stripped)
        if translated:
            hits += 1
            output.append(translated)
        else:
            misses += 1
            output.append(token)
    return "".join(output), hits, misses


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    buffer = ""
    for ch in text:
        if ch.isalnum() or ch in ("'", "-"):
            buffer += ch
        else:
            if buffer:
                tokens.append((buffer, "word"))
                buffer = ""
            tokens.append((ch, "punct"))
    if buffer:
        tokens.append((buffer, "word"))
    return tokens


def apply_en_to_ko_grammar(text: str) -> str:
    text = re.sub(r"\bI am ([^\\s]+)", r"나는 \\1이다", text, flags=re.IGNORECASE)
    text = re.sub(r"\bYou are ([^\\s]+)", r"너는 \\1이다", text, flags=re.IGNORECASE)
    return text


def strip_korean_particles(token: str) -> str:
    particles = ("은", "는", "이", "가", "을", "를", "에", "에서", "과", "와", "도", "만")
    for particle in particles:
        if token.endswith(particle):
            return token[: -len(particle)]
    return token


def strip_korean_endings(token: str) -> str:
    endings = ("입니다", "해요", "하세요", "했어요")
    for ending in endings:
        if token.endswith(ending):
            return token[: -len(ending)]
    return token
