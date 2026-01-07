# Translation + Vocabulary PWA

Local, mobile-friendly English ↔ Korean translation and vocabulary trainer. FastAPI backend serves a vanilla JS frontend with PWA support and SQLite persistence.

## Project layout
```
translation_vocab_app/
  backend/
    app.py            # FastAPI entrypoint
    db.py             # SQLite helpers + initializer
    models.sql        # DB schema
    services/
      translate.py    # Pluggable translation provider (local_nmt + localdict)
      vocab.py        # Vocabulary CRUD + scoring helpers
    requirements.txt
  frontend/
    index.html
    app.js
    styles.css
    pwa/
      manifest.json
      service-worker.js
      icon-192.txt
      icon-512.txt
```

## Run instructions
1) `cd translation_vocab_app/backend`  
2) Create & activate a virtual environment:  
   - Windows: `python -m venv venv && venv\\Scripts\\activate`  
   - macOS/Linux: `python -m venv venv && source venv/bin/activate`  
3) Install dependencies: `pip install -r requirements.txt`  
4) Start the server: `uvicorn app:app --port 8000`  
5) Open http://localhost:8000 in your browser. The backend serves the frontend directly, so CORS is not required.
6) To run backend tests: `pytest`

## Features
- Translation + enrichment (IPA, related forms, phrases, examples) using a local translation CLI with a dictionary fallback.
- Auto-translate: typing/paste triggers translation after a short debounce (default ~600ms). “Translate” button remains as a manual fallback.
- Provider selection + automatic fallback chain (`cli` → `localdict`) with latency + provider diagnostics shown in the UI and `/api/health`.
- Direction selector: force EN→KO, KO→EN, or Auto detection (Korean characters → KO source; Latin letters → EN source).
- Notebook auto-saves successful translations into a dedicated SQLite database, with search + direction filters and book-style pagination.
- SQLite persistence; database file is created automatically on first run. Optional `/api/seed` endpoint seeds sample data.
- PWA manifest + service worker for offline-friendly usage; “Install app” prompt supported when eligible.

## UI navigation
- Bottom navigation toggles between **Translate** and **Notebook** views within the same page.
- Translate view: pick a provider (Auto/cli/localdict/placeholder), view provider_used + latency, and see clear error messages when translation fails.
- Notebook uses a two-page “open book” layout (left/right pages) with a visible spine, page numbers, and a subtle slide animation when flipping pages.

## API overview
- `POST /api/translate` – translate and optionally save `{ text, note, save }`.
- `POST /api/vocab` – create a vocab entry.
- `GET /api/notes` – list note names.
- `GET /api/vocab?note=daily` – list vocab items.
- `DELETE /api/vocab/{id}` – delete entry.
- `POST /api/vocab/{id}/wrong/increment` – increment wrong count (color-coded).
- `POST /api/vocab/{id}/wrong/reset` – reset wrong count.
- `POST /api/vocab/{id}/attempt` – record O/X attempt and success rate.
- `GET /api/notebook` – list auto-saved translations with pagination and filters.
- `DELETE /api/notebook/{id}` – remove a notebook entry.

## Clipboard behavior
Browsers cannot watch the clipboard continuously. The UI provides a **Paste** button plus auto-translate on input/paste events (and Ctrl+V where supported).

## Dictionary files
Local dictionary files live in `translation_vocab_app/backend/services/dictionaries/`:
- `en_ko.json` for English → Korean
- `ko_en.json` for Korean → English

**Format**
```json
{
  "hello": "안녕하세요",
  "invite": "초대"
}
```

The server caches dictionaries but reloads automatically if the files change timestamps. Restart the server if you replace the files entirely to ensure a clean reload.

## Local translation CLI
Set `TRANSLATE_CLI_PATH` to the local CLI executable:
- Windows (PowerShell): `$env:TRANSLATE_CLI_PATH="C:\\Path\\To\\translator.exe"`
- macOS/Linux: `export TRANSLATE_CLI_PATH=/path/to/translator`

The CLI must accept:
```
<TRANSLATE_CLI_PATH> --src <src_lang> --dest <dest_lang> --text "<text>"
```

And output JSON like:
```json
{"translated": "...", "provider_used": "cli", "engine": "argos"}
```

See `tools/dummy_translate_cli.py` for a local dev stub.

## Notebook auto-save
Each `/api/translate` call evaluates `translation_success`. Successful translations are upserted into
`backend/data/notebook.sqlite` keyed by `(src_lang, dest_lang, original_normalized)`. If the same
entry repeats, the `count` and `last_seen_at` are updated.

Success rules (summary):
- provider_used must be `local_nmt` or `localdict` (with dictionary hits)
- translation must be non-empty and not a placeholder
- translated must differ from normalized original (unless target script is detected)
