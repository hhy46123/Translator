from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "notebook.sqlite"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_notebook_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notebook_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                src_lang TEXT NOT NULL,
                dest_lang TEXT NOT NULL,
                original TEXT NOT NULL,
                translated TEXT NOT NULL,
                provider_used TEXT NOT NULL,
                note TEXT,
                count INTEGER DEFAULT 1,
                original_normalized TEXT NOT NULL,
                UNIQUE(src_lang, dest_lang, original_normalized)
            )
            """
        )
        conn.commit()


def normalize_original(text: str, src_lang: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    if src_lang == "en":
        return normalized.lower()
    return normalized


def upsert_entry(
    src_lang: str,
    dest_lang: str,
    original: str,
    translated: str,
    provider_used: str,
    note: str | None = None,
) -> dict[str, Any]:
    original_norm = normalize_original(original, src_lang)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO notebook_entries (
                src_lang, dest_lang, original, translated, provider_used, note, original_normalized
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(src_lang, dest_lang, original_normalized)
            DO UPDATE SET
                last_seen_at = CURRENT_TIMESTAMP,
                translated = excluded.translated,
                provider_used = excluded.provider_used,
                note = COALESCE(excluded.note, notebook_entries.note),
                count = notebook_entries.count + 1
            """,
            (
                src_lang,
                dest_lang,
                original,
                translated,
                provider_used,
                note,
                original_norm,
            ),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT * FROM notebook_entries
            WHERE src_lang = ? AND dest_lang = ? AND original_normalized = ?
            """,
            (src_lang, dest_lang, original_norm),
        ).fetchone()
        return dict(row)


def list_notebook(
    page: int = 1,
    page_size: int = 40,
    query: str | None = None,
    direction: str = "all",
) -> tuple[list[dict[str, Any]], int]:
    offset = (page - 1) * page_size
    where = []
    params: list[Any] = []
    if query:
        where.append("(original LIKE ? OR translated LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    if direction in {"en_ko", "ko_en"}:
        src, dest = direction.split("_")
        where.append("src_lang = ? AND dest_lang = ?")
        params.extend([src, dest])
    where_clause = f\"WHERE {' AND '.join(where)}\" if where else \"\"

    with get_connection() as conn:
        total = conn.execute(
            f\"SELECT COUNT(*) as c FROM notebook_entries {where_clause}\",
            params,
        ).fetchone()[\"c\"]
        rows = conn.execute(
            f\"SELECT * FROM notebook_entries {where_clause} ORDER BY last_seen_at DESC LIMIT ? OFFSET ?\",
            (*params, page_size, offset),
        ).fetchall()
        return [dict(row) for row in rows], total


def delete_entry(entry_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM notebook_entries WHERE id = ?", (entry_id,))
        conn.commit()
