CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    summary TEXT,
    category TEXT,
    image_url TEXT,
    source_name TEXT,
    source_url TEXT,
    published_at DATETIME,
    is_featured BOOLEAN DEFAULT 0,
    trending_score REAL DEFAULT 0
);

-- NAYA: har article do source links (A aur B) se banta hai, lekin 'articles' table mein
-- sirf ek (source_url) store hoti thi. Isse dusra link "unused" maana jaata tha aur
-- dusri category mein dobara use ho jaata tha (same story alag headline se 3-4 baar chhap jaati thi).
-- Ye table dono links permanently record karti hai taaki wo kabhi dobara use na hon.
CREATE TABLE IF NOT EXISTS used_source_links (
    link TEXT PRIMARY KEY,
    used_at DATETIME
);
