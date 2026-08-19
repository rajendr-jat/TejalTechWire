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

def generate_full_article(titles_text, category):
    if not client:
        return "AI content generation skipped.", "Tech Update", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600"
    try:
        # Gemini ko bol rahe hain ki poori detail mein article likho
        prompt = f"""
        You are a lead tech journalist for 'TejalTechWire'. 
        Based on these recent headlines from the '{category}' sector:
        {titles_text}
        
        Write a comprehensive, professional, and detailed news article (at least 3 paragraphs long) covering this trend thoroughly. 
        Also, give it a compelling, professional News Headline.
        
        Format your response strictly like this:
        TITLE: [Your professional headline here]
        CONTENT: [Your detailed multi-paragraph news article here]
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
            new_title = "Major Shift in Technology Landscape"
            new_content = text
            
        # Category ke hisaab se ek high-quality relevant image set karna
        if category == "AI & ML":
            image_url = "https://images.unsplash.com/photo-1677442136019-21780efad99a?w=600"
        elif category == "EV":
            image_url = "https://images.unsplash.com/photo-1558448987-4354c2518e3c?w=600"
        else:
            image_url = "https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=600"
            
        return new_content, new_title, image_url
            
    except Exception as e:
        return f"Detailed reporting on upcoming tech milestones.", "Industry Insights", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600"

def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        recent_titles = [entry.title for entry in feed.entries[:3]]
        
        if not recent_titles:
            continue
            
        titles_combined = "\n- " + "\n- ".join(recent_titles)
        
        print(f"Generating full original article for {category}...")
        content, title, image_url = generate_full_article(titles_combined, category)
        
        source_url = "#"
        source_name = "TejalTechWire News Desk"
        
        # Check duplicate by title
        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            continue
            
        cursor.execute("""
            INSERT OR IGNORE INTO articles (title, summary, category, image_url, source_name, source_url, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, content, category, image_url, source_name, source_url, datetime.now().isoformat()))
        print(f"Published Full Article: {title}")
            
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
    print("Starting TejalTechWire Full Article Engine...")
    db_conn = setup_db()
    fetch_and_process(db_conn)
    export_to_json(db_conn)
    db_conn.close()
    print("Generation Complete!")
    
