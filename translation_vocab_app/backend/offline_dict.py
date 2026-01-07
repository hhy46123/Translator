from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import zipfile
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = Path(os.getenv("OFFLINE_DICT_CACHE_DIR", str(BASE_DIR / "data" / "cache")))
CACHE_PATH = CACHE_DIR / "offline_dict.sqlite"


def resolve_zip_path() -> Path:
    env_path = os.getenv("OFFLINE_DICT_ZIP_PATH")
    if env_path:
        zip_path = Path(env_path).expanduser()
        if zip_path.exists():
            return zip_path
        raise RuntimeError(
            "OFFLINE_DICT_ZIP_PATH is set but the file does not exist. "
            "Set it in PowerShell: $env:OFFLINE_DICT_ZIP_PATH=\"C:\\path\\to\\dict.zip\""
        )

    search_dirs = [
        BASE_DIR / "data",
        BASE_DIR.parent / "data",
        Path.cwd(),
        Path.home() / "Downloads",
        Path.home() / "Documents",
    ]
    for directory in search_dirs:
        zip_candidate = _find_zip_in_dir(directory)
        if zip_candidate:
            return zip_candidate

    raise RuntimeError(
        "Offline dictionary zip not found. Set OFFLINE_DICT_ZIP_PATH in PowerShell: "
        "$env:OFFLINE_DICT_ZIP_PATH=\"C:\\path\\to\\dict.zip\""
    )


def _find_zip_in_dir(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    for path in directory.glob("*.zip"):
        if _zip_contains_json(path):
            return path
    return None


def _zip_contains_json(zip_path: Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    return True
    except zipfile.BadZipFile:
        return False
    return False


def ensure_index() -> Path:
    zip_path = resolve_zip_path()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_PATH.exists():
        current = _read_meta(CACHE_PATH)
        if current.get("zip_size") == str(zip_path.stat().st_size) and current.get("zip_mtime") == str(
            zip_path.stat().st_mtime
        ):
            return CACHE_PATH
    build_index(zip_path, CACHE_PATH)
    return CACHE_PATH


def build_index(zip_path: Path, sqlite_path: Path) -> None:
    logger.info("Building offline dictionary index from %s", zip_path)
    if sqlite_path.exists():
        sqlite_path.unlink()
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "CREATE TABLE entry (id INTEGER PRIMARY KEY, ko TEXT NOT NULL, definition_ko TEXT)"
        )
        conn.execute(
            "CREATE TABLE en_map (entry_id INTEGER NOT NULL, en TEXT NOT NULL, en_norm TEXT NOT NULL)"
        )
        conn.execute("CREATE INDEX idx_entry_ko ON entry(ko)")
        conn.execute("CREATE INDEX idx_en_map_en ON en_map(en_norm)")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")

        entry_count = 0
        map_count = 0
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                with zf.open(name) as handle:
                    payload = json.load(handle)
                for entry in _iter_entries(payload):
                    ko = entry.get("ko")
                    en_list = entry.get("en", [])
                    if not ko or not en_list:
                        continue
                    definition = entry.get("definition_ko") or ""
                    cursor = conn.execute(
                        "INSERT INTO entry (ko, definition_ko) VALUES (?, ?)", (ko, definition)
                    )
                    entry_id = cursor.lastrowid
                    entry_count += 1
                    for en in en_list:
                        en_norm = normalize_en(en)
                        if not en_norm:
                            continue
                        conn.execute(
                            "INSERT INTO en_map (entry_id, en, en_norm) VALUES (?, ?, ?)",
                            (entry_id, en, en_norm),
                        )
                        map_count += 1

        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            [
                ("zip_size", str(zip_path.stat().st_size)),
                ("zip_mtime", str(zip_path.stat().st_mtime)),
                ("entry_count", str(entry_count)),
                ("map_count", str(map_count)),
            ],
        )
    logger.info("Offline dictionary index built: %s entries, %s mappings", entry_count, map_count)


def _read_meta(sqlite_path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        with sqlite3.connect(sqlite_path) as conn:
            for key, value in conn.execute("SELECT key, value FROM meta"):
                data[key] = value
    except sqlite3.Error:
        return {}
    return data


def _iter_entries(payload: dict) -> Iterable[dict]:
    lexical_resource = payload.get("LexicalResource", {})
    lexicon = lexical_resource.get("Lexicon", {})
    entries = lexicon.get("LexicalEntry", []) or []
    if isinstance(entries, dict):
        entries = [entries]
    for entry in entries:
        lemma = entry.get("Lemma", {})
        ko = _get_feat_value(lemma.get("feat", []), "writtenForm")
        if not ko:
            continue
        senses = entry.get("Sense", []) or []
        if isinstance(senses, dict):
            senses = [senses]
        definitions = _collect_definitions(senses)
        equivalents = _collect_equivalents(senses)
        yield {
            "ko": ko.strip(),
            "definition_ko": " / ".join(definitions),
            "en": equivalents,
        }


def _collect_definitions(senses: Iterable[dict]) -> list[str]:
    definitions: list[str] = []
    for sense in senses:
        definition = _get_feat_value(sense.get("feat", []), "definition")
        if definition:
            definitions.append(definition)
    return definitions


def _collect_equivalents(senses: Iterable[dict]) -> list[str]:
    equivalents: list[str] = []
    seen: set[str] = set()
    for sense in senses:
        eq_items = sense.get("Equivalent", []) or []
        if isinstance(eq_items, dict):
            eq_items = [eq_items]
        for eq in eq_items:
            language = _get_feat_value(eq.get("feat", []), "language")
            lemma = _get_feat_value(eq.get("feat", []), "lemma")
            if language == "영어" and lemma:
                key = lemma.strip()
                if key and key not in seen:
                    equivalents.append(key)
                    seen.add(key)
    return equivalents


def _get_feat_value(feats: Iterable[dict] | dict, att: str) -> str | None:
    if isinstance(feats, dict):
        if feats.get("att") == att:
            return feats.get("val")
        return None
    for feat in feats:
        if feat.get("att") == att:
            return feat.get("val")
    return None


def lookup_ko(query: str, limit: int = 5) -> list[dict]:
    if not query or not query.strip():
        return []
    normalized = query.strip()
    sqlite_path = ensure_index()
    with sqlite3.connect(sqlite_path) as conn:
        results = _search_ko(conn, normalized, limit)
        if results:
            return _hydrate_results(conn, results)
        results = _search_ko(conn, normalized, limit, prefix=True)
        if results:
            return _hydrate_results(conn, results)
        results = _search_ko(conn, normalized, limit, substring=True)
        return _hydrate_results(conn, results)


def lookup_en(query: str, limit: int = 5) -> list[dict]:
    if not query or not query.strip():
        return []
    normalized = normalize_en(query)
    if not normalized:
        return []
    sqlite_path = ensure_index()
    candidates = _english_candidates(normalized)
    with sqlite3.connect(sqlite_path) as conn:
        results = _search_en(conn, candidates, limit)
        if results:
            return _hydrate_results(conn, results)
        results = _search_en(conn, candidates, limit, prefix=True)
        if results:
            return _hydrate_results(conn, results)
        results = _search_en(conn, candidates, limit, substring=True)
        return _hydrate_results(conn, results)


def _search_ko(conn: sqlite3.Connection, term: str, limit: int, prefix: bool = False, substring: bool = False):
    if prefix:
        term = f"{term}%"
        clause = "ko LIKE ?"
    elif substring:
        term = f"%{term}%"
        clause = "ko LIKE ?"
    else:
        clause = "ko = ?"
    return list(conn.execute(f"SELECT id, ko, definition_ko FROM entry WHERE {clause} LIMIT ?", (term, limit)))


def _search_en(
    conn: sqlite3.Connection,
    terms: list[str],
    limit: int,
    prefix: bool = False,
    substring: bool = False,
):
    seen: set[int] = set()
    matches: list[tuple[int, str, str]] = []
    for term in terms:
        if prefix:
            clause = "en_norm LIKE ?"
            param = f"{term}%"
        elif substring:
            clause = "en_norm LIKE ?"
            param = f"%{term}%"
        else:
            clause = "en_norm = ?"
            param = term
        rows = conn.execute(
            f"""
            SELECT entry.id, entry.ko, entry.definition_ko
            FROM entry
            JOIN en_map ON entry.id = en_map.entry_id
            WHERE {clause}
            LIMIT ?
            """,
            (param, limit),
        ).fetchall()
        for row in rows:
            if row[0] in seen:
                continue
            seen.add(row[0])
            matches.append(row)
            if len(matches) >= limit:
                return matches
    return matches


def _hydrate_results(conn: sqlite3.Connection, entries: list[tuple[int, str, str]]):
    results = []
    for entry_id, ko, definition in entries:
        en_rows = conn.execute(
            "SELECT en FROM en_map WHERE entry_id = ? ORDER BY en", (entry_id,)
        ).fetchall()
        en_list = [row[0] for row in en_rows]
        results.append(
            {
                "ko": ko,
                "en": en_list,
                "definition_ko": definition or "",
            }
        )
    return results


def normalize_en(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^[\\W_]+|[\\W_]+$", "", cleaned)
    cleaned = re.sub(r"\\s+", " ", cleaned)
    return cleaned


def _english_candidates(base: str) -> list[str]:
    candidates = [base]
    candidates.extend(_apply_stemming_rules(base))
    deduped = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _apply_stemming_rules(value: str) -> list[str]:
    variants = []
    irregular = {
        "went": "go",
        "gone": "go",
        "better": "good",
        "best": "good",
        "worse": "bad",
        "worst": "bad",
        "children": "child",
        "men": "man",
        "women": "woman",
    }
    if value in irregular:
        variants.append(irregular[value])
    if value.endswith("ies") and len(value) > 4:
        variants.append(value[:-3] + "y")
    if value.endswith("ing") and len(value) > 4:
        variants.append(value[:-3])
    if value.endswith("ed") and len(value) > 3:
        variants.append(value[:-2])
    if value.endswith("s") and len(value) > 3:
        variants.append(value[:-1])
    return variants
