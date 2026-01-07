from __future__ import annotations

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import json
from urllib.parse import urlencode
from urllib.request import urlopen, Request


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


class GoogleTransProvider(TranslationProvider):
    name = "googletrans"

    def __init__(self) -> None:
        try:
            from googletrans import Translator  # type: ignore
        except Exception:  # pragma: no cover
            self.translator = None
        else:
            self.translator = Translator()

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        if not self.translator:
            raise RuntimeError("googletrans unavailable")

        def _task():
            detection = self.translator.detect(text)
            src = detection.lang or src_lang
            dest = dest_lang
            translation = self.translator.translate(text, src=src, dest=dest)
            return translation.text, detection.lang

        translated_text, detected = run_with_timeout(_task, timeout=timeout)
        return ProviderOutput(
            translated=translated_text,
            provider_name=self.name,
            raw_info={"detected": detected},
        )


class HttpFallbackProvider(TranslationProvider):
    name = "http_fallback"
    ENDPOINT = "https://api.mymemory.translated.net/get"

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        params = {"q": text, "langpair": f"{src_lang}|{dest_lang}"}
        query = urlencode(params)
        req = Request(f"{self.ENDPOINT}?{query}")
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        translated = data.get("responseData", {}).get("translatedText")
        if not translated:
            raise RuntimeError("empty translation from http fallback")
        return ProviderOutput(
            translated=translated,
            provider_name=self.name,
            raw_info={"endpoint": self.ENDPOINT, "matches": data.get("matches")},
        )


class OfflineProvider(TranslationProvider):
    name = "offline"

    def __init__(self) -> None:
        self.en_to_ko = {
            "hello": "안녕하세요",
            "hi": "안녕",
            "love": "사랑",
            "apple": "사과",
            "water": "물",
            "study": "공부하다",
            "food": "음식",
            "book": "책",
        }
        self.ko_to_en = {v: k for k, v in self.en_to_ko.items()}
        # extend manual pairs
        self.ko_to_en.update(
            {
                "사랑": "love",
                "안녕하세요": "hello",
                "안녕": "hi",
                "고마워요": "thank you",
                "감사합니다": "thank you",
                "물": "water",
                "사과": "apple",
                "공부하다": "study",
                "음식": "food",
                "책": "book",
            }
        )

    def translate(self, text: str, src_lang: str, dest_lang: str, timeout: int = 5) -> ProviderOutput:
        key = text.strip()
        if src_lang.startswith("en"):
            translated = self.en_to_ko.get(key.lower())
            if not translated:
                translated = f"오프라인 번역: {key}"
        else:
            translated = self.ko_to_en.get(key)
            if not translated:
                translated = f"Offline translation: {key}"
        return ProviderOutput(translated=translated, provider_name=self.name, raw_info={"offline": True})

    def health_check(self) -> Tuple[bool, str]:
        return True, "ok"


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

    providers = {
        "googletrans": GoogleTransProvider(),
        "http_fallback": HttpFallbackProvider(),
        "offline": OfflineProvider(),
    }
    order = ["googletrans", "http_fallback", "offline"]
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
            translated=f"[offline] unable to translate now: {text}",
            provider_name="offline",
            raw_info={"fallback": True},
        )

    ipa_text = generate_ipa(text, src_lang)
    related = generate_related(text, src_lang, dest_lang)

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
    providers = [GoogleTransProvider(), HttpFallbackProvider(), OfflineProvider()]
    status = {}
    for provider in providers:
        ok, message = provider.health_check()
        status[provider.name] = {"ok": ok, "message": message}
    return status
