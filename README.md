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
      translate.py    # Pluggable translation provider (DeepL + offline fallback)
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

## DeepL configuration
Set environment variables before running the server:
- `DEEPL_API_KEY` (required for online translation)
- `DEEPL_API_URL` (optional, default: `https://api-free.deepl.com/v2/translate`)

## Features
- Translation + enrichment (IPA, related forms, phrases, examples) with pluggable providers and offline-safe fallback.
- Auto-translate: typing/paste triggers translation after a short debounce (default ~600ms). “Translate” button remains as a manual fallback.
- Provider selection + automatic fallback chain (`deepl` → `googletrans` → `http_fallback` → offline dictionary) with latency + provider diagnostics shown in the UI and `/api/health`.
- Direction selector: force EN→KO, KO→EN, or Auto detection (Korean characters → KO source; Latin letters → EN source).
- Vocabulary notebook with notes/categories (`daily`, `vocab`, or custom), wrong-count tracking, success rate, O/X grading modal, and book-style two-page spreads (20 items per page, 40 per spread) with Prev/Next + arrow-key navigation.
- SQLite persistence; database file is created automatically on first run. Optional `/api/seed` endpoint seeds sample data.
- PWA manifest + service worker for offline-friendly usage; “Install app” prompt supported when eligible.

## UI navigation
- Bottom navigation toggles between **Translate** and **Notebook** views within the same page.
- Translate view: pick a provider (Auto/deepl/googletrans/http_fallback/offline), view provider_used + latency, and see clear error messages when translation fails.
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

## Clipboard behavior
Browsers cannot watch the clipboard continuously. The UI provides a **Paste** button plus auto-translate on input/paste events (and Ctrl+V where supported).
