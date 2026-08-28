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

-- har article do source links (A aur B) se banta hai, lekin 'articles' table mein
-- sirf ek (source_url) store hoti thi. Isse dusra link "unused" maana jaata tha aur
-- dusri category mein dobara use ho jaata tha (same story alag headline se 3-4 baar chhap jaati thi).
-- Ye table dono links permanently record karti hai taaki wo kabhi dobara use na hon.
CREATE TABLE IF NOT EXISTS used_source_links (
    link TEXT PRIMARY KEY,
    used_at DATETIME
);

-- Draft Review System. Naya article seedhe 'articles' (live/published) mein nahi jaata,
-- pehle yahan "pending review" ke roop mein aata hai. Sirf tumhare Approve karne ke baad hi
-- ye 'articles' table mein copy hota hai aur website par dikhta hai.
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    summary TEXT,
    category TEXT,
    image_url TEXT,
    source_name TEXT,
    source_url TEXT,
    trending_score REAL DEFAULT 0,
    created_at DATETIME
);
