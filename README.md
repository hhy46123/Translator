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
      translate.py    # Translation provider (Argos CLI + offline dictionary)
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
- Offline translation using a local Argos CLI plus an offline dictionary index built from the Korean Basic Dictionary zip.
- Auto-translate: typing/paste triggers translation after a short debounce (default ~600ms). “Translate” button remains as a manual fallback.
- Provider selection + automatic fallback chain (`argos` → `offline`) with latency + provider diagnostics shown in the UI and `/api/health`.
- Direction selector: force EN→KO, KO→EN, or Auto detection (Korean characters → KO source; Latin letters → EN source).
- Notebook auto-saves successful translations into a dedicated SQLite database, with search + direction filters and book-style pagination.
- SQLite persistence; database file is created automatically on first run. Optional `/api/seed` endpoint seeds sample data.
- PWA manifest + service worker for offline-friendly usage; “Install app” prompt supported when eligible.

## UI navigation
- Bottom navigation toggles between **Translate** and **Notebook** views within the same page.
- Translate view: pick a provider (Auto/argos/offline), view provider_used + latency, and see clear error messages when translation fails.
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

## Offline dictionary setup (required)
The backend reads the Korean Basic Dictionary JSON zip and builds a local SQLite index for fast offline lookups.

**PowerShell setup**
```powershell
$env:OFFLINE_DICT_ZIP_PATH="C:\\path\\to\\korean_basic_dictionary.zip"
$env:OFFLINE_ONLY=1
```

If `OFFLINE_DICT_ZIP_PATH` is not set, the backend auto-searches:
```
backend/data/
data/
current working directory
~/Downloads
~/Documents
```

The cache is stored at `translation_vocab_app/backend/data/cache/offline_dict.sqlite` and is rebuilt only when the zip changes.

## Local Argos CLI
The backend runs the bundled Argos CLI script:
```
python translation_vocab_app/backend/tools/translator_cli.py en ko "Hello world"
```
It prints only the translated string to stdout.

## Notebook auto-save
Each `/api/translate` call evaluates `translation_success`. Successful translations are upserted into
`backend/data/notebook.sqlite` keyed by `(src_lang, dest_lang, original_normalized)`. If the same
entry repeats, the `count` and `last_seen_at` are updated.

Success rules (summary):
- translation must be non-empty
- translated must differ from the original (after trimming)

## Example calls
```bash
curl -X POST http://localhost:8000/api/translate \\
  -H "Content-Type: application/json" \\
  -d '{"text":"가장자리","direction":"ko_to_en","provider":"offline"}'
```

```bash
curl -X POST http://localhost:8000/api/translate \\
  -H "Content-Type: application/json" \\
  -d '{"text":"edge","direction":"en_to_ko","provider":"offline"}'
```
