import sqlite3
from pathlib import Path

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


def seed_sample_data():
    sample_rows = [
        ("daily", "hello", "안녕하세요", ["hello there", "hello friend"], ["Hello, how are you?"]),
        ("vocab", "study", "공부하다", ["self-study", "study group"], ["I study Korean every evening."]),
    ]
    with get_connection() as conn:
        for note, eng, kor, phrases, examples in sample_rows:
            conn.execute(
                """
                INSERT INTO vocab_items (note, english, korean, phrases, examples)
                VALUES (?, ?, ?, ?, ?)
                """,
                (note, eng, kor, json_dumps(phrases), json_dumps(examples)),
            )
        conn.commit()


def json_dumps(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)

