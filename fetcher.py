import os
import json
import sqlite3
import feedparser
import trafilatura
from datetime import datetime
from google import genai

# Setup Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# Har category ke liye 2 ALAG source feeds — dono se poora article uthake AI merge karega
SOURCES = {
    "AI": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/",
    ],
    "Tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
    ],
    "Gadgets": [
        "https://www.engadget.com/rss.xml",
        "https://gizmodo.com/rss",
    ],
}

FALLBACK_IMAGES = {
    "AI": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=900&q=80",
    "Tech": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=900&q=80",
    "Gadgets": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=900&q=80",
}

DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    return conn


def fetch_full_article(url):
    """Diye gaye URL se poora article text + image nikalta hai (sirf RSS snippet nahi)."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None
        text = trafilatura.extract(downloaded)
        image_url = None
        try:
            meta = trafilatura.extract_metadata(downloaded)
            if meta and meta.image:
                image_url = meta.image
        except Exception:
            pass
        return text, image_url
    except Exception as e:
        print(f"Full article fetch failed for {url}: {e}")
        return None, None


def get_latest_entry_with_text(feed_url):
    """Feed ka sabse latest entry uthake uska poora text fetch karta hai."""
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:5]:
        link = entry.get("link")
        if not link:
            continue
        text, image_url = fetch_full_article(link)
        if text and len(text) > 200:
            return {
                "title": entry.get("title", ""),
                "text": text[:4000],   # prompt size seemit rakhne ke liye trim
                "image": image_url,
                "link": link,
            }
    return None


def generate_merged_article(article_a, article_b, category):
    if not client:
        return "Gemini API key missing, content generation skipped.", "TejalTechWire Special", FALLBACK_IMAGES.get(category, "")
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

        Also, provide a single English search keyword or short phrase (like 'electric car', 'smartphone', 'artificial intelligence robot') that best matches the visual theme of this news for a stock photo search.

        --- SOURCE A: "{article_a['title']}" ---
        {article_a['text']}

        --- SOURCE B: "{article_b['title']}" ---
        {article_b['text']}

        Format your response strictly as:
        TITLE: [Your new original catchy headline]
        KEYWORD: [1-3 words visual search keyword]
        CONTENT: [Your full original article]
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash', # Aapke original code ke mutabik model name
            contents=prompt
        )

        text = response.text.strip()
        if "TITLE:" in text and "KEYWORD:" in text and "CONTENT:" in text:
            parts = text.split("KEYWORD:")
            new_title = parts[0].replace("TITLE:", "").strip()
            
            rest = parts[1].split("CONTENT:")
            keyword = rest[0].strip().replace(" ", ",")
            new_content = rest[1].strip()
            
            # Unsplash Dynamic Image based on Gemini's keyword
            image_url = f"https://images.unsplash.com/featured/?{keyword}&w=900&q=80"
            return new_content, new_title, image_url
        else:
            return text, f"{category} Roundup", FALLBACK_IMAGES.get(category, "")

    except Exception as e:
        print(f"Gemini generation failed: {e}")
        return "Autonomous generation in progress. Stay tuned for updates.", f"{category} Update - {datetime.now().strftime('%d %b %Y %H:%M')}", FALLBACK_IMAGES.get(category, "")


def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)

    for category, feed_urls in SOURCES.items():
        if len(feed_urls) < 2:
            continue

        print(f"Fetching source A for {category}...")
        article_a = get_latest_entry_with_text(feed_urls[0])
        print(f"Fetching source B for {category}...")
        article_b = get_latest_entry_with_text(feed_urls[1])

        if not article_a or not article_b:
            print(f"Skipping {category}: couldn't get full text from both sources")
            continue

        print(f"Merging {category} articles with Gemini...")
        summary, title, ai_image_url = generate_merged_article(article_a, article_b, category)

        # Priority: 1. Original Article A Image -> 2. Original Article B Image -> 3. Gemini Dynamic Unsplash Keyword Image -> 4. Fallback
        image_url = article_a.get("image") or article_b.get("image") or ai_image_url or FALLBACK_IMAGES.get(category, "")

        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            print(f"Duplicate title skipped: {title}")
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, summary, category, image_url, "TejalTechWire Original", "#", datetime.now().isoformat()))
        print(f"Published Original: {title}")

    conn.commit()


def export_to_json(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published_at DESC LIMIT 30")
    articles = [dict(row) for row in cursor.fetchall()]

    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=4)
    print("Exported to JSON successfully!")


if __name__ == "__main__":
    print("Starting TejalTechWire Autonomous Content Engine...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    db_conn.close()
    print("Generation Complete!")
    
