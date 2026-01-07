from __future__ import annotations

import json
from typing import Dict, List, Optional

from db import get_connection, json_dumps


def serialize_row(row) -> Dict:
    return {
        "id": row["id"],
        "note": row["note"],
        "english": row["english"],
        "korean": row["korean"],
        "phrases": json.loads(row["phrases"] or "[]"),
        "examples": json.loads(row["examples"] or "[]"),
        "noun_forms": json.loads(row["noun_forms"] or "[]") if "noun_forms" in row.keys() else [],
        "verb_forms": json.loads(row["verb_forms"] or "[]") if "verb_forms" in row.keys() else [],
        "adj_forms": json.loads(row["adj_forms"] or "[]") if "adj_forms" in row.keys() else [],
        "ipa": row["ipa"] if "ipa" in row.keys() else "",
        "wrong_count": row["wrong_count"],
        "attempts_total": row["attempts_total"],
        "attempts_correct": row["attempts_correct"],
        "success_rate": calculate_success_rate(row["attempts_correct"], row["attempts_total"]),
    }


def calculate_success_rate(correct: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((correct / total) * 100, 2)


def wrong_color(count: int) -> str:
    if count == 0:
        return "gray"
    if count == 1:
        return "red"
    if count == 2:
        return "orange"
    if count == 3:
        return "yellow"
    return "green"


def list_notes() -> List[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT note FROM vocab_items ORDER BY note").fetchall()
        return [row["note"] for row in rows]


def list_vocab(note: Optional[str] = None, offset: int = 0, limit: int = 40) -> tuple[List[Dict], int]:
    with get_connection() as conn:
        params = []
        where_clause = ""
        if note:
            where_clause = "WHERE note = ?"
            params.append(note)

        total = conn.execute(f"SELECT COUNT(*) as c FROM vocab_items {where_clause}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM vocab_items {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [serialize_row(row) for row in rows], total


def create_vocab(
    english: str,
    korean: str,
    note: str,
    phrases=None,
    examples=None,
    noun_forms=None,
    verb_forms=None,
    adj_forms=None,
    ipa: str | None = "",
) -> Dict:
    phrases = phrases or []
    examples = examples or []
    noun_forms = noun_forms or []
    verb_forms = verb_forms or []
    adj_forms = adj_forms or []
    ipa = ipa or ""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO vocab_items (english, korean, note, phrases, examples, noun_forms, verb_forms, adj_forms, ipa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                english,
                korean,
                note,
                json_dumps(phrases),
                json_dumps(examples),
                json_dumps(noun_forms),
                json_dumps(verb_forms),
                json_dumps(adj_forms),
                ipa,
            ),
        )
        conn.commit()
        item_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM vocab_items WHERE id = ?", (item_id,)).fetchone()
        return serialize_row(row)


def delete_vocab(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM vocab_items WHERE id = ?", (item_id,))
        conn.commit()


def increment_wrong(item_id: int) -> Dict:
    with get_connection() as conn:
        conn.execute(
            "UPDATE vocab_items SET wrong_count = wrong_count + 1 WHERE id = ?",
            (item_id,),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM vocab_items WHERE id = ?", (item_id,)).fetchone()
        data = serialize_row(row)
        data["wrong_color"] = wrong_color(data["wrong_count"])
        return data


def reset_wrong(item_id: int) -> Dict:
    with get_connection() as conn:
        conn.execute("UPDATE vocab_items SET wrong_count = 0 WHERE id = ?", (item_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM vocab_items WHERE id = ?", (item_id,)).fetchone()
        data = serialize_row(row)
        data["wrong_color"] = wrong_color(data["wrong_count"])
        return data


def record_attempt(item_id: int, result: str) -> Dict:
    increment_correct = 1 if result.upper() == "O" else 0
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE vocab_items
            SET attempts_total = attempts_total + 1,
                attempts_correct = attempts_correct + ?
            WHERE id = ?
            """,
            (increment_correct, item_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM vocab_items WHERE id = ?", (item_id,)).fetchone()
        data = serialize_row(row)
        data["success_rate"] = calculate_success_rate(data["attempts_correct"], data["attempts_total"])
        return data
