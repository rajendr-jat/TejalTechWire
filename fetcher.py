import os
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

DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"

def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    return conn

def extract_image_from_entry(entry):
    # RSS feed se asli image nikalne ka tareeka
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')
    if 'links' in entry:
        for link in entry.links:
            if 'image' in link.get('type', ''):
                return link.get('href')
    # Agar feed mein image tag na mile, toh description/content se dhundho ya default tech image do
    return "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800"

def generate_professional_article(titles_text, category):
    if not client:
        return "Content generation unavailable.", "Tech Brief", ""
    try:
        prompt = f"""
        You are a top-tier tech journalist for 'TejalTechWire'. 
        Based on these latest updates from the '{category}' sector:
        {titles_text}
        
        Write a comprehensive, highly professional, multi-paragraph news article. 
        It must include:
        1. A catchy, professional News Headline.
        2. A structured body with sub-headings and bullet points where necessary (like a professional tech magazine).
        
        Format your response strictly as:
        TITLE: [Your headline here]
        CONTENT: [Your detailed article here using HTML tags like <h3>, <p>, <ul>, <li> for styling]
        """
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        text = response.text.strip()
        if "TITLE:" in text and "CONTENT:" in text:
            parts = text.split("CONTENT:")
            new_title = parts[0].replace("TITLE:", "").strip()
            new_content = parts[1].strip()
            return new_content, new_title
        else:
            return text, "Tech Industry Update"
            
    except Exception as e:
        return "<p>Detailed reporting in progress.</p>", "Breaking Tech News"

def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        if not feed.entries:
            continue
            
        # Pehli entry se asli image nikal lo
        entry = feed.entries[0]
        image_url = extract_image_from_entry(entry)
        
        recent_titles = [e.title for e in feed.entries[:3]]
        titles_combined = "\n- " + "\n- ".join(recent_titles)
        
        print(f"Generating professional article for {category}...")
        content, title = generate_professional_article(titles_combined, category)
        
        source_name = "TejalTechWire Bureau"
        source_url = "#"
        
        # Check duplicate
        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            continue
            
        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, content, category, image_url, source_name, source_url, datetime.now().isoformat()))
        print(f"Published: {title}")
            
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
    print("Starting TejalTechWire Engine...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    db_conn.close()
    print("Done!")
    
