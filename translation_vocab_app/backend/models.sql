CREATE TABLE IF NOT EXISTS vocab_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT DEFAULT 'daily',
    english TEXT NOT NULL,
    korean TEXT NOT NULL,
    phrases TEXT DEFAULT '[]',
    examples TEXT DEFAULT '[]',
    wrong_count INTEGER DEFAULT 0,
    attempts_total INTEGER DEFAULT 0,
    attempts_correct INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
