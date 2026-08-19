import os
import re
import json
import sqlite3
import feedparser
from datetime import datetime
from google import genai

# Setup Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

FEEDS = {
    "AI & ML": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "EV": "https://electrek.co/feed/",
    "Gadgets": "https://www.theverge.com/rss/index.xml"
}

# Fallback image agar kisi feed entry mein image na mile
FALLBACK_IMAGES = {
    "AI & ML": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&q=80",
    "EV": "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=800&q=80",
    "Gadgets": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
}

DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    return conn


def extract_image_from_entry(entry):
    """RSS entry se real image URL nikalta hai (media tags, enclosures, ya HTML content se)."""
    try:
        if hasattr(entry, "media_content") and entry.media_content:
            url = entry.media_content[0].get("url")
            if url:
                return url
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            url = entry.media_thumbnail[0].get("url")
            if url:
                return url
        for link in getattr(entry, "links", []):
            if link.get("type", "").startswith("image"):
                return link.get("href")
        html_blob = ""
        if hasattr(entry, "content") and entry.content:
            html_blob = entry.content[0].get("value", "")
        elif hasattr(entry, "summary"):
            html_blob = entry.summary
        match = re.search(r'<img[^>]+src="([^"]+)"', html_blob)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def generate_original_article(titles_text, category):
    if not client:
        return "Gemini API key missing, content generation skipped.", "TejalTechWire Special"
    try:
        # Gemini ko bol rahe hain ki in titles ko mix karke ek nayi original, poori news likho
        prompt = f"""
        You are an expert tech journalist writing a full news report for 'TejalTechWire'.
        Take these recent headlines/topics from the '{category}' sector:
        {titles_text}

        Write a complete, well-structured original news article (250-350 words, 3-4 full paragraphs)
        that combines and expands on these ideas into a fresh, informative report. Include context,
        why it matters, and a natural concluding thought. Do not just summarize in one line — write it
        like a full published news story.

        Also give it a catchy, original headline.

        Format your response strictly as:
        TITLE: [Your new catchy title here]
        CONTENT: [Your full generated article here]
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
            return text, "Latest Tech Breakthrough"

    except Exception as e:
        print(f"Gemini generation failed: {e}")
        return "Autonomous generation in progress. Stay tuned for updates.", f"{category} Update - {datetime.now().strftime('%d %b %Y %H:%M')}"


def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)

    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        top_entries = feed.entries[:4]
        recent_titles = [entry.title for entry in top_entries]

        if not recent_titles:
            continue

        titles_combined = "\n- " + "\n- ".join(recent_titles)

        # Pehle entry se real image nikalne ki koshish, warna fallback
        image_url = None
        for entry in top_entries:
            image_url = extract_image_from_entry(entry)
            if image_url:
                break
        if not image_url:
            image_url = FALLBACK_IMAGES.get(category, "")

        print(f"Generating original mix article for {category}...")
        summary, title = generate_original_article(titles_combined, category)

        source_url = "#"
        source_name = "TejalTechWire Original"

        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, summary, category, image_url, source_name, source_url, datetime.now().isoformat()))
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
    
