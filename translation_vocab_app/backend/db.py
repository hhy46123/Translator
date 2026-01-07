import sqlite3
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "vocab.db"
SCHEMA_PATH = BASE_DIR / "models.sql"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn, open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
        conn.executescript(schema_file.read())
        conn.commit()
        _ensure_columns(conn)


def seed_sample_data():
    sample_rows = [
        ("daily", "hello", "안녕하세요", ["hello there", "hello friend"], ["Hello, how are you?"]),
        ("vocab", "study", "공부하다", ["self-study", "study group"], ["I study Korean every evening."]),
    ]
    with get_connection() as conn:
        for note, eng, kor, phrases, examples in sample_rows:
            conn.execute(
                """
                INSERT INTO vocab_items (note, english, korean, phrases, examples, noun_forms, verb_forms, adj_forms, ipa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note,
                    eng,
                    kor,
                    json_dumps(phrases),
                    json_dumps(examples),
                    json_dumps([]),
                    json_dumps([]),
                    json_dumps([]),
                    "",
                ),
            )
        conn.commit()


def json_dumps(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)


def _ensure_columns(conn):
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(vocab_items)")}
    wanted_defaults = {
        "noun_forms": "TEXT DEFAULT '[]'",
        "verb_forms": "TEXT DEFAULT '[]'",
        "adj_forms": "TEXT DEFAULT '[]'",
        "ipa": "TEXT DEFAULT ''",
    }
    for column, definition in wanted_defaults.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE vocab_items ADD COLUMN {column} {definition}")
    conn.commit()
