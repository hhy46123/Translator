from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional


def _contains_korean(text: str) -> bool:
    return bool(re.search("[\uac00-\ud7af]", text))


@dataclass
class TranslationResult:
    src_lang: str
    dest_lang: str
    original: str
    translated: str
    ipa: str
    related: Dict[str, List[str]]


class TranslationProvider:
    def translate(self, text: str) -> TranslationResult:
        raise NotImplementedError


class GoogleTransProvider(TranslationProvider):
    def __init__(self) -> None:
        try:
            from googletrans import Translator  # type: ignore
        except Exception:  # pragma: no cover - graceful fallback
            self.translator = None
        else:
            self.translator = Translator()

    def translate(self, text: str) -> TranslationResult:
        if self.translator:
            detection = self.translator.detect(text)
            src_lang = detection.lang or "en"
            dest_lang = "ko" if src_lang.startswith("en") else "en"
            translation = self.translator.translate(text, src=src_lang, dest=dest_lang)
            translated_text = translation.text
        else:
            src_lang = "ko" if _contains_korean(text) else "en"
            dest_lang = "en" if src_lang == "ko" else "ko"
            translated_text = f"[{dest_lang} translation unavailable offline] {text}"

        ipa_text = generate_ipa(text, src_lang)
        related = generate_related(text, src_lang, dest_lang)

        return TranslationResult(
            src_lang=src_lang,
            dest_lang=dest_lang,
            original=text,
            translated=translated_text,
            ipa=ipa_text,
            related=related,
        )


class SimpleStubProvider(TranslationProvider):
    def translate(self, text: str) -> TranslationResult:
        src_lang = "ko" if _contains_korean(text) else "en"
        dest_lang = "en" if src_lang == "ko" else "ko"
        translated_text = f"[{dest_lang} placeholder] {text}"
        ipa_text = generate_ipa(text, src_lang)
        related = generate_related(text, src_lang, dest_lang)

        return TranslationResult(
            src_lang=src_lang,
            dest_lang=dest_lang,
            original=text,
            translated=translated_text,
            ipa=ipa_text,
            related=related,
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
    # naive English approximation
    phonetic = " ".join([syllable.lower() for syllable in re.findall(r"[a-zA-Z']+", text) or [text]])
    return f"[en] /{phonetic}/"


def get_provider() -> TranslationProvider:
    provider = GoogleTransProvider()
    if getattr(provider, "translator", None) is not None:
        return provider
    return provider if provider.translator is not None else SimpleStubProvider()


def translate_text(text: str) -> TranslationResult:
    provider = get_provider()
    return provider.translate(text)
