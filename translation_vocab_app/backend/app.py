from __future__ import annotations

from pathlib import Path
import re
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db import init_db, seed_sample_data
from services.notebook import (
    delete_entry,
    init_notebook_db,
    list_notebook,
    upsert_entry,
)
from services.translate import providers_health, translate_text
from services.vocab import (
    create_vocab,
    delete_vocab,
    increment_wrong,
    list_notes,
    list_vocab,
    record_attempt,
    reset_wrong,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="Translation + Vocabulary App")


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    note: Optional[str] = "daily"
    save: bool = False
    provider: Optional[str] = "auto"
    direction: Optional[str] = "auto"


class VocabCreateRequest(BaseModel):
    english: str
    korean: str
    note: str = "daily"
    phrases: list[str] = []
    examples: list[str] = []


class AttemptRequest(BaseModel):
    result: str


@app.on_event("startup")
def startup_event():
    init_db()
    init_notebook_db()


@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount(
    "/pwa",
    StaticFiles(directory=FRONTEND_DIR / "pwa"),
    name="pwa",
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")


@app.post("/api/translate")
def translate(req: TranslateRequest):
    result = translate_text(req.text, preferred_provider=req.provider, direction=req.direction or "auto")
    translation_success, save_reason = evaluate_translation_success(result)
    save_attempted = False
    notebook_saved = False
    saved_entry = None
    if translation_success:
        save_attempted = True
        saved_entry = upsert_entry(
            src_lang=result.src_lang,
            dest_lang=result.dest_lang,
            original=result.original,
            translated=result.translated,
            provider_used=result.provider_used,
            note=req.note,
        )
        notebook_saved = True
        save_reason = "success"

    if req.save:
        saved = create_vocab(
            english=result.original if result.src_lang.startswith("en") else result.translated,
            korean=result.original if result.src_lang.startswith("ko") else result.translated,
            note=req.note or "daily",
            phrases=result.related.get("phrases", []),
            examples=result.related.get("examples", []),
            noun_forms=result.related.get("noun_forms", []),
            verb_forms=result.related.get("verb_forms", []),
            adj_forms=result.related.get("adj_forms", []),
            ipa=result.ipa,
        )
        saved_payload = saved
    else:
        saved_payload = None
    return {
        "src_lang": result.src_lang,
        "dest_lang": result.dest_lang,
        "original": result.original,
        "translated": result.translated,
        "ipa": result.ipa,
        "related": result.related,
        "provider_used": result.provider_used,
        "latency_ms": result.latency_ms,
        "error_chain": result.error_chain,
        "raw_info": result.raw_info,
        "saved": notebook_saved,
        "saved_vocab": saved_payload,
        "translation_success": translation_success,
        "save_attempted": save_attempted,
        "saved_entry": saved_entry,
        "save_reason": save_reason,
    }


@app.post("/api/vocab")
def save_vocab(req: VocabCreateRequest):
    return create_vocab(req.english, req.korean, req.note, req.phrases, req.examples)


@app.get("/api/notes")
def get_notes():
    return {"notes": list_notes()}


@app.get("/api/vocab")
def get_vocab(note: Optional[str] = None, offset: int = 0, limit: int = 40):
    items, total_count = list_vocab(note, offset, limit)
    return {"items": items, "total_count": total_count}


@app.delete("/api/vocab/{item_id}")
def remove_vocab(item_id: int):
    delete_vocab(item_id)
    return {"deleted": item_id}


@app.post("/api/vocab/{item_id}/wrong/increment")
def increase_wrong(item_id: int):
    return increment_wrong(item_id)


@app.post("/api/vocab/{item_id}/wrong/reset")
def reset_wrong_count(item_id: int):
    return reset_wrong(item_id)


@app.post("/api/vocab/{item_id}/attempt")
def attempt(item_id: int, req: AttemptRequest):
    if req.result.upper() not in {"O", "X"}:
        raise HTTPException(status_code=400, detail="Result must be 'O' or 'X'")
    return record_attempt(item_id, req.result.upper())


@app.post("/api/seed")
def seed():
    seed_sample_data()
    return {"seeded": True}


@app.get("/api/health")
def health():
    status = providers_health()
    return {
        "server_ok": True,
        "providers": {
            name: {"ok": info["ok"], "message": info["message"]}
            for name, info in status.items()
            if name not in {"argos_models_dir"}
        },
        "argos_models_dir": status.get("argos_models_dir", ""),
        "last_error": None,
    }


@app.get("/api/notebook")
def notebook(
    page: int = 1,
    page_size: int = 40,
    query: Optional[str] = None,
    direction: str = "all",
):
    items, total = list_notebook(page=page, page_size=page_size, query=query, direction=direction)
    return {"items": items, "total_count": total}


@app.delete("/api/notebook/{entry_id}")
def delete_notebook_entry(entry_id: int):
    delete_entry(entry_id)
    return {"deleted": entry_id}


def evaluate_translation_success(result) -> tuple[bool, str]:
    provider_allowed = {"argos", "localdict"}
    if result.provider_used not in provider_allowed:
        for err in result.error_chain:
            lowered = err.lower()
            if "localdict miss" in lowered:
                return False, "miss_localdict"
            if "argos models" in lowered or "argos translate not installed" in lowered:
                return False, "provider_error"
        return False, "provider_error"
    if not result.translated:
        return False, "provider_error"
    placeholder_prefixes = ("오프라인 번역:", "[offline]")
    if result.translated.strip().startswith(placeholder_prefixes):
        return False, "placeholder"

    normalized_original = normalize_text(result.original, result.src_lang)
    normalized_translated = normalize_text(result.translated, result.dest_lang)
    if normalized_original == normalized_translated:
        if result.src_lang != result.dest_lang:
            if result.dest_lang == "ko" and contains_korean(result.translated):
                return True, "success"
            if result.dest_lang == "en" and contains_latin(result.translated):
                return True, "success"
        return False, "echo_original"

    for err in result.error_chain:
        lowered = err.lower()
        if "ssl" in lowered or "certificate" in lowered or "network" in lowered or "unavailable" in lowered:
            return False, "provider_error"

    if result.provider_used == "localdict":
        hits = 0
        if isinstance(result.raw_info, dict):
            hits = result.raw_info.get("hits", 0)
        if hits == 0:
            return False, "miss_localdict"

    return True, "success"


def normalize_text(text: str, lang: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    if lang == "en":
        return normalized.lower()
    return normalized


def contains_korean(text: str) -> bool:
    return bool(re.search("[\uac00-\ud7af]", text))


def contains_latin(text: str) -> bool:
    return bool(re.search("[a-zA-Z]", text))
