import os
import json
import sqlite3
import feedparser
from datetime import datetime
from google import genai

# Setup Gemini API (GitHub Secrets se uthayega)
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# RSS Feeds (AI, EV aur Gadgets ki news)
FEEDS = {
    "AI & ML": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "EV": "https://electrek.co/feed/",
    "Gadgets": "https://www.theverge.com/rss/index.xml"
}

DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"

def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    return conn

def summarize_with_gemini(text):
    if not client:
        return "Summary generation skipped (No API Key)."
    try:
        prompt = f"Summarize this tech news in 2-3 short, engaging lines. Keep it objective and factual. News: {text}"
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Summary available on source site."

def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        # Sirf latest 3 news uthayenge har feed se
        for entry in feed.entries[:3]:
            source_url = entry.link
            
            # Check duplicate in DB
            cursor.execute("SELECT id FROM articles WHERE source_url = ?", (source_url,))
            if cursor.fetchone():
                continue
                
            title = entry.title
            source_name = url.split('/')[2]
            summary = summarize_with_gemini(title)
            image_url = "https://via.placeholder.com/400x200?text=TejalTechWire"
            
            cursor.execute("""
                INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, summary, category, image_url, source_name, source_url, datetime.now().isoformat()))
            print(f"Saved: {title}")
            
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
    print("Starting TejalTechWire Fetcher...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    db_conn.close()
    print("Update Complete!")
    
