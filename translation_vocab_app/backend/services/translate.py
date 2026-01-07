from __future__ import annotations

import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import subprocess
import sys
from pathlib import Path

from offline_dict import lookup_en, lookup_ko

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
    results: List[dict]
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


class CliProvider(TranslationProvider):
    name = "argos"

    def __init__(self) -> None:
        self.cli_path = Path(__file__).resolve().parents[1] / "tools" / "translator_cli.py"

    def is_ready(self) -> bool:
        return self.cli_path.exists()

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 10) -> ProviderOutput:
        if not self.cli_path.exists():
            raise RuntimeError(f"translator_cli not found: {self.cli_path}")

        if len(text) > 5000:
            raise RuntimeError("input too long (max 5000 chars)")

        try:
            result = subprocess.run(
                [sys.executable, str(self.cli_path), src_lang, dest_lang, text],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("cli timeout") from exc
        except Exception as exc:  # pragma: no cover - unexpected
            raise RuntimeError(f"cli execution failed: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"cli failed: {stderr or 'non-zero exit'}")

        translated = (result.stdout or "").strip()
        if not translated:
            raise RuntimeError("cli returned empty translation")

        return ProviderOutput(translated=translated, provider_name=self.name, raw_info={"engine": "argos"})


class OfflineProvider(TranslationProvider):
    name = "offline"

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        if src_lang == "ko":
            results = lookup_ko(text)
            translated = ", ".join(results[0]["en"]) if results else ""
        else:
            results = lookup_en(text)
            translated = ", ".join([entry["ko"] for entry in results]) if results else ""
        return ProviderOutput(
            translated=translated,
            provider_name=self.name,
            raw_info={"results": results},
        )


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

    cli_provider = CliProvider()
    offline_provider = OfflineProvider()

    providers = {"argos": cli_provider, "offline": offline_provider}
    order = ["argos", "offline"]
    normalized_preference = preferred_provider
    if preferred_provider == "cli":
        normalized_preference = "argos"
    if os.getenv("OFFLINE_ONLY") == "1":
        normalized_preference = "offline"
        order = ["offline"]
    elif normalized_preference and normalized_preference != "auto" and normalized_preference in providers:
        if normalized_preference == "offline":
            order = ["offline"]
        else:
            order = [normalized_preference] + [p for p in order if p != normalized_preference]

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
            translated="",
            provider_name="argos",
            raw_info={"fallback": True},
        )

    ipa_text = generate_ipa(text, src_lang)
    related = generate_related(text, src_lang, dest_lang)

    if chosen.provider_name == "argos":
        error_chain.append("argos used")
    if chosen.provider_name == "offline":
        error_chain.append("offline used")

    results = []
    if isinstance(chosen.raw_info, dict):
        results = chosen.raw_info.get("results", [])

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
        results=results,
        raw_info=chosen.raw_info,
    )


def run_with_timeout(func, timeout: int = 5):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        return future.result(timeout=timeout)


def providers_health():
    cli_provider = CliProvider()
    providers = [cli_provider, OfflineProvider()]
    status = {}
    for provider in providers:
        ok, message = provider.health_check()
        status[provider.name] = {"ok": ok, "message": message}
    status["cli_ready"] = cli_provider.is_ready()
    status["cli_path_detected"] = str(cli_provider.cli_path)
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
