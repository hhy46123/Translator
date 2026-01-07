from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from db import init_db, seed_sample_data
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
        "saved": saved_payload,
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
            if name != "deepl_key_present"
        },
        "deepl_key_present": status.get("deepl_key_present", False),
        "last_error": None,
    }
