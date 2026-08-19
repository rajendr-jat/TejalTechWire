import os
import feedparser
from datetime import datetime
import google.generativeai as genai

# API key configure karna (GitHub Secrets se uthayega)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY nahi mili!")
    exit(1)

genai.configure(api_key=api_key)

# Stable aur working model select kiya hai
model = genai.GenerativeModel('gemini-1.5-flash')

# RSS Feeds (AI, EV aur Gadgets ki news ke liye)
FEEDS = {
    "AI & ML": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "EV": "https://electrek.co/feed/",
    "Gadgets": "https://www.theverge.com/rss/index.xml"
}

print("Starting TejalTechWire News Fetcher...")

all_articles = []

# Har feed se latest 3-3 news nikalna
for category, url in FEEDS.items():
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            
            # Gemini se choti aur acchi summary banwana
            prompt = f"Summarize this tech news in 2 short, engaging lines. Keep it objective. Title: {title}"
            try:
                response = model.generate_content(prompt)
                summary = response.text.strip()
            except Exception:
                summary = "Click to read full news on source website."
            
            all_articles.append({
                "title": title,
                "summary": summary,
                "category": category,
                "link": link
            })
            print(f"Fetched: {title}")
    except Exception as e:
        print(f"Error fetching {category}: {e}")

# HTML Cards banana
cards_html = ""
for item in all_articles:
    cards_html += f"""
    <div style="background: #1e293b; color: #f8fafc; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border: 1px solid #334155;">
        <span style="background: #3b82f6; color: white; padding: 4px 10px; font-size: 12px; border-radius: 20px; font-weight: bold;">{item['category']}</span>
        <h3 style="margin: 15px 0 10px 0; font-size: 18px; line-height: 1.4;"><a href="{item['link']}" target="_blank" style="color: #60a5fa; text-decoration: none;">{item['title']}</a></h3>
        <p style="color: #94a3b8; font-size: 14px; line-height: 1.6; margin-bottom: 15px;">{item['summary']}</p>
        <a href="{item['link']}" target="_blank" style="color: #38bdf8; font-size: 14px; text-decoration: none; font-weight: bold;">Read More →</a>
    </div>
    """

# Poori khubsurat index.html file ka design
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TejalTechWire - Live Tech News</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f1f5f9; margin: 0; padding: 20px; }}
        header {{ text-align: center; padding: 40px 0; border-bottom: 1px solid #1e293b; margin-bottom: 40px; }}
        h1 {{ font-size: 32px; color: #38bdf8; margin: 0; }}
        p.subtitle {{ color: #94a3b8; margin-top: 10px; font-size: 16px; }}
        .container {{ max-width: 1000px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        footer {{ text-align: center; margin-top: 50px; color: #64748b; font-size: 14px; }}
    </style>
</head>
<body>
    <header>
        <h1>TejalTechWire</h1>
        <p class="subtitle">Your 24/7 Automated Source for AI, EV & Gadget News</p>
        <p style="font-size: 12px; color: #64748b; margin-top: 5px;">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </header>
    
    <div class="container">
        {cards_html}
    </div>

    <footer>
        <p>© 2026 TejalTechWire. Powered by Gemini & GitHub Actions.</p>
    </footer>
</body>
</html>
"""

# Seedha index.html mein save karna
with open("index.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Success! index.html updated successfully with fresh news.")
