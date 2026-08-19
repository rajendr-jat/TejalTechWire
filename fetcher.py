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
    else:
        # Fallback schema creation if schema.sql is missing
        conn.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE,
                summary TEXT,
                category TEXT,
                image_url TEXT,
                source_name TEXT,
                source_url TEXT,
                published_at TEXT
            )
        ''')
        conn.commit()
    return conn

def synthesize_article(titles_text, category):
    if not client:
        return "<p>Detailed tech analysis and background reporting on current market shifts.</p>", "The Evolution of Modern Technology", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800"
    
    try:
        prompt = f"""
        You are an expert lead technology journalist for 'TejalTechWire'. 
        Based on these recent headlines and updates from the '{category}' sector:
        {titles_text}
        
        Write a comprehensive, highly professional, multi-paragraph original news article. 
        It must include:
        1. A catchy, professional editorial Headline.
        2. A structured body with professional paragraphs and <h3> subheadings where necessary (Medium magazine style).
        
        Format your response strictly as:
        TITLE: [Your unique headline here]
        CONTENT: [Your detailed article here using HTML tags like <p>, <h3>, <ul>, <li>]
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
        else:
            new_title = f"Latest Trends in {category}"
            new_content = text
            
        # Category ke hisaab se stunning editorial image assign karna
        if category == "AI & ML":
            image_url = "https://images.unsplash.com/photo-1677442136019-21780efad99a?w=800"
        elif category == "EV":
            image_url = "https://images.unsplash.com/photo-1558448987-4354c2518e3c?w=800"
        else:
            image_url = "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=800"
            
        return new_content, new_title, image_url
            
    except Exception as e:
        return "<p>Continuous reporting and deep-dive analysis into emerging technological frameworks.</p>", "Industry Insights", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800"

def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        if not feed.entries:
            continue
            
        recent_titles = [entry.title for entry in feed.entries[:3]]
        titles_combined = "\n- " + "\n- ".join(recent_titles)
        
        print(f"Synthesizing editorial article for {category}...")
        content, title, image_url = synthesize_article(titles_combined, category)
        
        source_name = "TejalTechWire Editorial"
        source_url = "#"
        published_at = datetime.now().isoformat()
        
        # Check duplicate by title
        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            continue
            
        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, content, category, image_url, source_name, source_url, published_at))
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
    print("Starting TejalTechWire Backend Engine...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    db_conn.close()
    print("Backend Generation Complete!")
    
