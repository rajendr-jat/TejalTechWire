CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    summary TEXT,
    category TEXT,
    image_url TEXT,
    source_name TEXT,
    source_url TEXT,
    published_at DATETIME,
    is_featured BOOLEAN DEFAULT 0
);
