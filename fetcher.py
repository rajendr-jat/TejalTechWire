import os
import json
import sqlite3
import feedparser
import trafilatura
import requests
import random
import urllib.parse
from datetime import datetime
from google import genai

# Setup Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

SOURCES = {
    "AI": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.artificialintelligence-news.com/feed/",
        "https://www.marktechpost.com/feed/",
    ],
    "Tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://arstechnica.com/feed/",
    ],
    "Gadgets": [
        "https://www.engadget.com/rss.xml",
        "https://gizmodo.com/rss",
        "https://www.theverge.com/rss/index.xml",
        "https://www.slashgear.com/feed/",
    ],
}

FALLBACK_IMAGES = {
    "AI": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=900&q=80",
    "Tech": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=900&q=80",
    "Gadgets": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=900&q=80",
}

# --- TITLE-BASED SMART UNSPLASH IMAGE SYSTEM ---
def get_unsplash_image_by_title(title, category):
    """Article ke title ya keywords ke adhar par Unsplash se match karti hui image nikalta hai."""
    try:
        # Title ke kuch mukhya shabd nikalte hain (jaise tech, apple, robot, chip, ai)
        words = [w.lower() for w in title.split() if len(w) > 3]
        query_words = ",".join(words[:3]) if words else category.lower()
        
        encoded_query = urllib.parse.quote(f"{query_words},technology")
        random_sig = random.randint(1, 100000)
        # Unsplash ki dynamic source URL jo query ke mutabik photo degi
        return f"https://images.unsplash.com/featured/?{encoded_query}&sig={random_sig}&w=900&q=80"
    except Exception:
        return FALLBACK_IMAGES.get(category, "")
# -----------------------------------------------

DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"
SITE_URL = "https://tejaltechwire.pages.dev"

CAT_CLASS_MAP = {"AI": "ai", "Tech": "tech", "Gadgets": "gadgets"}

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — TejalTechWire</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta property="og:type" content="article">
<link rel="canonical" href="{url}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>

<header>
  <a class="logo" href="/">
    <div class="logo-mark">TW</div>
    <div class="logo-text">Tejal<span>Tech</span>Wire</div>
  </a>
  <button class="theme-toggle" id="themeBtn" onclick="toggleTheme()">☾</button>
</header>

<div class="container">
  <a class="back-link" href="/">← Back to TejalTechWire</a>
  <span class="cat-badge {cat_class}">{category}</span>
  <h1 class="article-title">{title}</h1>
  <div class="article-byline">
    <div class="avatar">{avatar}</div>
    <div class="byline-text">{source_name} · {time_str}</div>
  </div>
  <img class="article-hero-img" src="{image}" alt="{title}">
  <div class="article-text">{body_html}</div>
  <div class="article-source">{source_line}</div>
</div>

<footer>
  <p><span class="foot-brand">TejalTechWire</span> — Independent AI, Tech &amp; Gadget news desk. &copy; 2026.</p>
  <p><a href="/">Home</a></p>
</footer>

<script>
  const themeBtn = document.getElementById('themeBtn');
  let currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';
  function toggleTheme(){
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';
  }
</script>
</body>
</html>
"""


def _escape_html(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paragraphs_html(text):
    parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    if len(parts) <= 1:
        parts = [p.strip() for p in (text or "").split("\n") if p.strip()]
    return "".join(f"<p>{_escape_html(p)}</p>" for p in parts)


def _initials(name):
    if not name:
        return "TW"
    clean = name.replace("TejalTechWire", "TW")
    words = clean.split(" ")
    return "".join(w[0] for w in words[:2] if w).upper()[:2] or "TW"


def _time_ago(published_at):
    try:
        dt = datetime.fromisoformat(published_at)
        diff = datetime.now() - dt
        hrs = int(diff.total_seconds() // 3600)
        if hrs < 1:
            return f"{int(diff.total_seconds() // 60)}m ago"
        if hrs < 24:
            return f"{hrs}h ago"
        return f"{hrs // 24}d ago"
    except Exception:
        return ""


def generate_article_pages(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]

    os.makedirs("articles", exist_ok=True)

    for a in rows:
        image = a.get("image_url") or get_unsplash_image_by_title(a.get("title", ""), a.get("category", ""))
        description = _escape_html((a.get("summary") or "")[:160])
        cat_class = CAT_CLASS_MAP.get(a.get("category"), "gadgets")
        source_name = a.get("source_name") or "TejalTechWire Original"
        source_url = a.get("source_url")

        if source_url and source_url != "#":
            source_line = f'Source references: <a href="{source_url}" target="_blank">Visit original →</a>'
        else:
            source_line = "Original reporting by TejalTechWire, based on multiple industry sources."

        html = ARTICLE_TEMPLATE.format(
            title=_escape_html(a.get("title", "")),
            description=description,
            image=image,
            url=f"{SITE_URL}/articles/{a['id']}.html",
            cat_class=cat_class,
            category=_escape_html(a.get("category", "")),
            avatar=_initials(source_name),
            source_name=_escape_html(source_name),
            time_str=_time_ago(a.get("published_at", "")),
            body_html=_paragraphs_html(a.get("summary", "")),
            source_line=source_line,
        )

        with open(f"articles/{a['id']}.html", "w", encoding="utf-8") as f:
            f.write(html)

    return rows


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    return conn


def fetch_full_article(url):
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        if resp.status_code != 200 or not resp.text:
            return None
        return trafilatura.extract(resp.text)
    except Exception as e:
        print(f"Full article fetch failed for {url}: {e}")
        return None


def get_latest_entry_with_text(feed_url):
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        return None
    if not feed.entries:
        return None
    for entry in feed.entries[:8]:
        link = entry.get("link")
        if not link:
            continue
        text = fetch_full_article(link)
        if text and len(text) > 200:
            return {
                "title": entry.get("title", ""),
                "text": text[:4000],
                "link": link,
            }
    return None


def get_two_articles(feed_urls):
    collected = []
    for feed_url in feed_urls:
        entry = get_latest_entry_with_text(feed_url)
        if entry:
            collected.append(entry)
        if len(collected) >= 2:
            break
    return collected


def generate_merged_article(article_a, article_b, category):
    if not client:
        return "Gemini API key missing.", "TejalTechWire Special"
    try:
        prompt = f"""
        You are a senior tech journalist writing an original news report for 'TejalTechWire',
        a publication covering AI, Technology, and Gadgets.

        Below are two full source articles on related recent developments in the '{category}' space.
        Read both carefully, then write a brand-new, completely original article in your own words —
        combining the key facts, context, and angles from both. Do NOT copy any sentence or phrasing
        from the sources. Write like an experienced human journalist: a strong opening line, clear
        context on why it matters, concrete details, and a natural closing thought. Length: 300-400 words,
        3-5 paragraphs, no bullet points.

        --- SOURCE A: "{article_a['title']}" ---
        {article_a['text']}

        --- SOURCE B: "{article_b['title']}" ---
        {article_b['text']}

        Format your response strictly as:
        TITLE: [Your new original catchy headline]
        CONTENT: [Your full original article]
        """

        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )

        text = response.text.strip()
        if "TITLE:" in text and "CONTENT:" in text:
            parts = text.split("CONTENT:")
            new_title = parts[0].replace("TITLE:", "").strip()
            new_content = parts[1].strip()
            return new_content, new_title
        else:
            return text, f"{category} Roundup"

    except Exception as e:
        print(f"Gemini generation failed: {e}")
        return "Autonomous generation in progress.", f"{category} Update"


def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)

    for category, feed_urls in SOURCES.items():
        print(f"\n=== Processing category: {category} ===")
        articles = get_two_articles(feed_urls)

        if len(articles) < 2:
            continue

        article_a, article_b = articles[0], articles[1]

        summary, title = generate_merged_article(article_a, article_b, category)

        # Duplicate Checker Filter
        cursor.execute("SELECT id FROM articles WHERE title = ? OR summary LIKE ?", (title, f"%{title[:20]}%"))
        if cursor.fetchone():
            print(f"Duplicate/Similar article skipped to prevent repetition: {title}")
            continue

        # Title-based Unsplash Image Generation
        image_url = get_unsplash_image_by_title(title, category)

        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, summary, category, image_url, "TejalTechWire Original", "#", datetime.now().isoformat()))
        print(f"Published Unique Original with Title-Matched Image: {title}")

    conn.commit()


def export_to_json(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published_at DESC LIMIT 30")
    articles = [dict(row) for row in cursor.fetchall()]

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=4)
    print("Exported to JSON successfully!")


def generate_sitemap(article_rows=None):
    now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    url_entries = [f"""  <url>
    <loc>{SITE_URL}/</loc>
    <lastmod>{now}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>"""]

    for a in (article_rows or []):
        lastmod = (a.get("published_at") or "")[:10] or now[:10]
        url_entries.append(f"""  <url>
    <loc>{SITE_URL}/articles/{a['id']}.html</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(url_entries)}
</urlset>
"""
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(xml)
    print("sitemap.xml generated!")


def generate_robots_txt():
    content = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(content)
    print("robots.txt generated!")


if __name__ == "__main__":
    print("Starting TejalTechWire Clean Content Engine...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    all_rows = generate_article_pages(db_conn)
    generate_sitemap(all_rows)
    generate_robots_txt()
    db_conn.close()
    print("Generation Complete!")
    
