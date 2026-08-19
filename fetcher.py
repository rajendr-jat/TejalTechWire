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

def generate_original_article(titles_text, category):
    if not client:
        return "Gemini API key missing, content generation skipped.", "TejalTechWire Special"
    try:
        # Gemini ko bol rahe hain ki in titles ko mix karke ek nayi original news likho
        prompt = f"""
        You are an expert tech journalist for 'TejalTechWire'. 
        Take these recent headlines/topics from the '{category}' sector:
        {titles_text}
        
        Write a brand new, engaging, original short tech article (around 4-5 sentences) combining these ideas into a fresh perspective. 
        Also, give it a catchy new original Headline.
        
        Format your response strictly as:
        TITLE: [Your new catchy title here]
        CONTENT: [Your generated original article here]
        """
        
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt
        )
        
        text = response.text.strip()
        # Parse Title and Content
        if "TITLE:" in text and "CONTENT:" in text:
            parts = text.split("CONTENT:")
            new_title = parts[0].replace("TITLE:", "").strip()
            new_content = parts[1].strip()
            return new_content, new_title
        else:
            return text, "Latest Tech Breakthrough"
            
    except Exception as e:
        # Print the real error so it shows up in GitHub Actions logs instead of failing silently
        print(f"Gemini generation failed: {e}")
        return f"Autonomous generation in progress. Stay tuned for updates.", f"{category} Update - {datetime.now().strftime('%d %b %Y %H:%M')}"

def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    
    for category, url in FEEDS.items():
        feed = feedparser.parse(url)
        # Top 4 news nikal kar unke titles ikatthe karenge
        recent_titles = [entry.title for entry in feed.entries[:4]]
        
        if not recent_titles:
            continue
            
        titles_combined = "\n- " + "\n- ".join(recent_titles)
        
        # Gemini se mix karke ek original article banwayenge
        print(f"Generating original mix article for {category}...")
        summary, title = generate_original_article(titles_combined, category)
        
        source_url = "#" # Ab doosri site par jaane ki zaroorat nahi, ye hamari k
