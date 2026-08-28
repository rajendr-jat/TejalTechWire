import os
import json
import sqlite3
import feedparser
import trafilatura
import requests
import random  # <-- Sirf ye add kiya hai random image system ke liye
import time
from datetime import datetime
from google import genai

# Setup Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

# --- NAYA: TRENDING/VIRAL DETECTION SYSTEM ---
# Sirf genuinely trending/viral stories hi publish hongi. Kam-score wali "boring" news
# skip ho jaayegi -- koi bhi random/filler article site par nahi jaayega.
MIN_TRENDING_SCORE = 30   # ise 0-100 ke beech tune kar sakte ho -- jitna zyada, utna strict

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "have", "will",
    "your", "what", "into", "over", "after", "about", "than", "then",
    "just", "more", "some", "when", "how", "why", "who", "its", "his",
    "her", "our", "their", "you", "are", "was", "were", "has", "had",
}


def _keywords(title):
    words = "".join(c if c.isalnum() else " " for c in (title or "").lower()).split()
    return {w for w in words if len(w) > 3 and w not in STOPWORDS}


def check_hackernews_score(title):
    """Hacker News (free, no API key) par check karta hai ki isi topic pe koi
    high-point/high-comment discussion hai ya nahi -- genuine tech-world trending signal."""
    try:
        cutoff = int(time.time()) - (3 * 86400)  # pichle 3 din
        query = " ".join(list(_keywords(title))[:8])
        if not query:
            return 0
        resp = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": "story", "numericFilters": f"created_at_i>{cutoff}"},
            timeout=10,
        )
        hits = resp.json().get("hits", [])
        if not hits:
            return 0
        max_points = max((h.get("points") or 0) for h in hits)
        max_comments = max((h.get("num_comments") or 0) for h in hits)
        score = min(40, max_points / 5) + min(10, max_comments / 5)
        return round(score, 1)
    except Exception as e:
        print(f"Hacker News check failed: {e}")
        return 0


def get_all_recent_titles():
    """Saari categories ki saari feeds se latest titles nikalta hai (ek hi baar poore
    run mein) -- isse pata chalta hai kitni ALAG websites isi topic ko cover kar rahi hain."""
    all_feeds = sorted({url for feeds in SOURCES.values() for url in feeds})
    titles_by_feed = []
    for feed_url in all_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                t = entry.get("title", "")
                if t:
                    titles_by_feed.append((feed_url, t))
        except Exception:
            continue
    return titles_by_feed


def count_overlap_sources(title, titles_by_feed):
    """Kitni ALAG feeds mein isi topic (2+ common significant keywords) ka mention hai."""
    my_kw = _keywords(title)
    if not my_kw:
        return 0
    matching_feeds = set()
    for feed_url, other_title in titles_by_feed:
        if len(my_kw & _keywords(other_title)) >= 2:
            matching_feeds.add(feed_url)
    return len(matching_feeds)


def compute_trending_score(title, titles_by_feed):
    """0-100 ka trending score -- Hacker News signal + kitni jagah cover ho raha hai, dono milakar."""
    hn_component = check_hackernews_score(title)
    overlap_count = count_overlap_sources(title, titles_by_feed)
    overlap_component = min(50, overlap_count * 15)
    total = min(100, hn_component + overlap_component)
    print(f"  Trending check: HN={hn_component}, sources-overlap={overlap_count} (+{overlap_component}) => total={total}")
    return total
# ------------------------------------------------


def are_related(title_a, title_b):
    """Check karta hai ki dono sources GENUINELY isi event ke baare mein hain ya nahi
    (kam se kam 1 common significant keyword). Agar unrelated hain (jaise "Apple headset"
    aur "drone ban" -- 2 alag stories), to inhe jabardasti mix NAHI karte."""
    return len(_keywords(title_a) & _keywords(title_b)) >= 1

# Bahut si news sites bina "real browser" jaisा User-Agent bheje request block kar deti hain.
# Isse fetch fail hota tha aur AI/Gadgets category skip ho jaati thi.
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# Har category ke liye MULTIPLE candidate feeds — agar ek source fail ho (block/down/empty)
# to code automatically agla try karta hai, isliye poori category skip nahi hoti.
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
    "Mobile": [
        "https://www.gsmarena.com/rss-news-reviews.php3",
        "https://www.androidauthority.com/feed/",
        "https://9to5mac.com/feed/",
        "https://www.androidpolice.com/feed/",
    ],
    "Business": [
        "https://www.cnbc.com/id/19854910/device/rss/rss.html",
        "https://www.businessinsider.com/tech/rss",
        "https://fortune.com/section/tech/feed/",
    ],
}

FALLBACK_IMAGES = {
    "AI": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=900&q=80",
    "Tech": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=900&q=80",
    "Gadgets": "https://images.unsplash.com/photo-1526738549149-8e07eca6c147?w=900&q=80",
    "Mobile": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=900&q=80",
    "Business": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=900&q=80",
}

# --- NAYA IMAGE SYSTEM: Unsplash (official API) primary, Pexels backup, fixed image final fallback ---
# Ab keyword sirf category-level nahi, balki Gemini article ka poora text padhkar deta hai
# (generate_merged_article ke IMAGE_KEYWORDS wale hisse se), isliye photo topic se zyada match karti hai.
# Random page + random result se variety milती hai, taaki same photo baar baar repeat na ho.
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY")

CATEGORY_IMAGE_KEYWORDS = {
    "AI": ["artificial intelligence", "machine learning technology", "robot automation", "data center servers"],
    "Tech": ["technology computer", "software startup", "computer chip", "modern office technology"],
    "Gadgets": ["smartphone gadget", "wearable technology", "laptop desk", "smart home device"],
    "Mobile": ["smartphone screen", "mobile phone hand", "app interface phone", "smartphone camera"],
    "Business": ["business meeting office", "stock market chart", "corporate skyscraper", "handshake business"],
}

# Isی run ke andar jo images use ho chuki, unhe dobara na chunne ke liye
_used_images_this_run = set()


def _search_unsplash(query):
    if not UNSPLASH_ACCESS_KEY:
        return None
    try:
        page = random.randint(1, 3)
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={
                "query": query,
                "per_page": 12,
                "page": page,
                "orientation": "landscape",
                "client_id": UNSPLASH_ACCESS_KEY,
            },
            timeout=10,
        )
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        random.shuffle(results)
        for photo in results:
            url = photo.get("urls", {}).get("regular")
            if url and url not in _used_images_this_run:
                return url
        # Sab pehle use ho chuki thi, majboori mein pehli hi de do
        return results[0].get("urls", {}).get("regular")
    except Exception as e:
        print(f"Unsplash fetch failed for '{query}': {e}")
        return None


def _search_pexels(query):
    if not PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 10, "orientation": "landscape"},
            timeout=10,
        )
        data = resp.json()
        photos = data.get("photos", [])
        if not photos:
            return None
        random.shuffle(photos)
        for photo in photos:
            url = photo.get("src", {}).get("large")
            if url and url not in _used_images_this_run:
                return url
        return photos[0].get("src", {}).get("large")
    except Exception as e:
        print(f"Pexels fetch failed for '{query}': {e}")
        return None


def get_stock_image(keyword, category):
    """Article ke TOPIC se match karta keyword lekar image dhoondhta hai:
    1) Unsplash se article-specific keyword  2) Unsplash se category keyword
    3) Pexels se article-specific keyword    4) Pexels se category keyword
    5) Fixed safe fallback image
    Sabse pehle jo bhi mile, wahi use hoti hai — copyright-free stock hi rehती hai."""
    candidates = [keyword] + random.sample(CATEGORY_IMAGE_KEYWORDS.get(category, ["technology"]), k=2)

    for kw in candidates:
        url = _search_unsplash(kw)
        if url:
            print(f"Unsplash image found for '{kw}'")
            _used_images_this_run.add(url)
            return url

    for kw in candidates:
        url = _search_pexels(kw)
        if url:
            print(f"Pexels image found for '{kw}'")
            _used_images_this_run.add(url)
            return url

    print("No API image found, using fixed fallback")
    return FALLBACK_IMAGES.get(category, "")


DB_FILE = "tejaltechwire.db"
JSON_FILE = "data/articles.json"
SITE_URL = "https://tejaltechwire.pages.dev"

# --- NAYA: Draft Review System ke GitHub links banane ke liye ---
# YE APNI REPO KE HISAAB SE THEEK KARNA: "username/repo-name" (jaisa github.com URL mein dikhta hai)
GITHUB_REPO = "rajendr-jat/TejalTechWire"
GITHUB_BRANCH = "main"


# --- NAYA: IndexNow protocol — Bing/Yandex ko turant "naya article aaya hai" batata hai,
# turant crawl ho jaata hai (Google ke liye ye kaam nahi karta, sirf sitemap se hi discover hota hai) ---
INDEXNOW_KEY = "tejaltechwire4f8a2c19"  # koi bhi unique random text ho sakta hai, ye fixed rehna chahiye


def generate_indexnow_key_file():
    """IndexNow ko verify karne ke liye ek file honi chahiye jiska naam hi key ho, jismein wahi key likhi ho."""
    with open(f"{INDEXNOW_KEY}.txt", "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def submit_indexnow(urls):
    """Bing/Yandex ko naye/updated URLs ke baare mein turant bata deta hai."""
    if not urls:
        return
    try:
        resp = requests.post(
            "https://api.indexnow.org/indexnow",
            json={
                "host": SITE_URL.replace("https://", "").replace("http://", ""),
                "key": INDEXNOW_KEY,
                "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
                "urlList": urls,
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        print(f"IndexNow submitted {len(urls)} URLs — status {resp.status_code}")
    except Exception as e:
        print(f"IndexNow submission failed: {e}")

CAT_CLASS_MAP = {"AI": "ai", "Tech": "tech", "Gadgets": "gadgets", "Mobile": "mobile", "Business": "business"}

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — TejalTechWire</title>
<meta name="description" content="{description}">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">

<!-- Open Graph (Facebook/WhatsApp share preview) -->
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="TejalTechWire">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">

<link rel="canonical" href="{url}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">

<!-- Structured Data: Google ko batata hai ye ek News Article hai (rich snippet ke liye) -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": {title_json},
  "image": [{image_json}],
  "datePublished": "{date_iso}",
  "dateModified": "{date_iso}",
  "author": [{{
    "@type": "Organization",
    "name": "TejalTechWire",
    "url": "{site_url}"
  }}],
  "publisher": {{
    "@type": "Organization",
    "name": "TejalTechWire",
    "logo": {{
      "@type": "ImageObject",
      "url": "{site_url}/assets/favicon.svg"
    }}
  }},
  "description": {description_json},
  "mainEntityOfPage": {{
    "@type": "WebPage",
    "@id": "{url}"
  }}
}}
</script>

<script async src="https://www.googletagmanager.com/gtag/js?id=G-SMW0JFM2W0"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-SMW0JFM2W0');
</script>
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
  {trending_badge}
  <h1 class="article-title">{title}</h1>
  <div class="article-byline">
    <div class="avatar">{avatar}</div>
    <div class="byline-text">{source_name} · {time_str}</div>
  </div>
  <img class="article-hero-img" src="{image}" alt="{title}">
  <div class="article-text">{body_html}</div>
  <div class="article-source">Original reporting by TejalTechWire, based on multiple industry sources.</div>

  <div class="related-section">
    <h2>More in {category}</h2>
    <div class="related-list">{related_html}</div>
  </div>
</div>

<footer>
  <p><span class="foot-brand">TejalTechWire</span> — Independent AI, Tech &amp; Gadget news desk. &copy; 2026.</p>
  <p><a href="/">Home</a> | <a href="/about.html">About</a> | <a href="/contact.html">Contact</a> | <a href="/privacy.html">Privacy Policy</a></p>
</footer>

<script>
  const themeBtn = document.getElementById('themeBtn');
  let currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';
  function toggleTheme(){{
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';
  }}
</script>
</body>
</html>
"""


def _escape_html(text):
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paragraphs_html(text):
    """Gemini ka structured output (HEADING:/Q:/A: markers ke saath) HTML mein convert karta hai
    -- headings <h2> ban jaate hain, Q:/A: pairs ek FAQ box ban jaate hain, baaki normal <p>."""
    blocks = [b.strip() for b in (text or "").split("\n\n") if b.strip()]
    if len(blocks) <= 1:
        blocks = [b.strip() for b in (text or "").split("\n") if b.strip()]

    html_parts = []
    for block in blocks:
        block_lines = block.splitlines()
        first_line = block_lines[0].strip()

        if first_line.upper().startswith("HEADING:"):
            heading_text = first_line.split(":", 1)[1].strip()
            rest = " ".join(l.strip() for l in block_lines[1:]).strip()
            html_parts.append(f"<h2>{_escape_html(heading_text)}</h2>")
            if rest:
                html_parts.append(f"<p>{_escape_html(rest)}</p>")

        elif first_line.upper().startswith("Q:"):
            q_text = first_line.split(":", 1)[1].strip()
            a_text = ""
            for l in block_lines[1:]:
                if l.strip().upper().startswith("A:"):
                    a_text = l.strip().split(":", 1)[1].strip()
            html_parts.append(
                f'<div class="faq-item"><p class="faq-q">{_escape_html(q_text)}</p>'
                f'<p class="faq-a">{_escape_html(a_text)}</p></div>'
            )
        else:
            html_parts.append(f"<p>{_escape_html(block)}</p>")

    return "".join(html_parts)


def _plain_summary(text, limit=160):
    """Meta description/JSON-LD ke liye HEADING:/Q:/A: markers hataakar plain text banata hai."""
    cleaned = (text or "").replace("HEADING:", " ").replace("Q:", " ").replace("A:", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


def _initials(name):
    if not name:
        return "TW"
    clean = name.replace("TejalTechWire", "TW")
    words = clean.split(" ")
    return "".join(w[0] for w in words[:2] if w).upper()[:2] or "TW"


def slugify(title):
    """Title ko URL-friendly slug mein badalta hai: 'Garmin Fenix 9 Launch!' -> 'garmin-fenix-9-launch'"""
    text = "".join(c if c.isalnum() else " " for c in (title or "").lower())
    words = [w for w in text.split() if w]
    return "-".join(words[:10])[:80] or "article"


def article_url_path(article_id, title):
    """Ab URL format: /articles/<id>-<slug>.html — ID hamesha unique/stable rehta hai,
    slug sirf readability/SEO ke liye extra hai."""
    return f"{article_id}-{slugify(title)}"


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


# --- NAYA: Homepage ab fetcher.py hi generate karta hai, articles ka HTML pehle se
# built-in hota hai (JS ke bharose nahi rehta). Isse Google/Bing turant homepage khulte
# hi saara content dekh lete hain, bina JavaScript render kiye — crawlability guaranteed. ---
HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TejalTechWire — AI, Tech & Gadget News</title>
<meta name="description" content="Original AI, Tech and Gadget news, written fresh every few hours.">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<link rel="canonical" href="{site_url}/">

<meta property="og:title" content="TejalTechWire — AI, Tech & Gadget News">
<meta property="og:description" content="Original AI, Tech and Gadget news, written fresh every few hours.">
<meta property="og:type" content="website">
<meta property="og:url" content="{site_url}/">
<meta property="og:site_name" content="TejalTechWire">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="TejalTechWire — AI, Tech & Gadget News">
<meta name="twitter:description" content="Original AI, Tech and Gadget news, written fresh every few hours.">

<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "NewsMediaOrganization",
  "name": "TejalTechWire",
  "url": "{site_url}/",
  "logo": "{site_url}/assets/favicon.svg",
  "description": "Original AI, Tech and Gadget news, written fresh every few hours."
}}
</script>
</head>
<body>

<header>
  <a class="logo" href="/">
    <div class="logo-mark">TW</div>
    <div class="logo-text">Tejal<span>Tech</span>Wire</div>
  </a>
  <nav id="nav-filters">
    <button class="pill active" onclick="filterNews('All', this)">All</button>
    <button class="pill" onclick="filterNews('AI', this)">AI</button>
    <button class="pill" onclick="filterNews('Tech', this)">Tech</button>
    <button class="pill" onclick="filterNews('Gadgets', this)">Gadgets</button>
    <button class="pill" onclick="filterNews('Mobile', this)">Mobile</button>
    <button class="pill" onclick="filterNews('Business', this)">Business</button>
  </nav>
  <button class="theme-toggle" id="themeBtn" onclick="toggleTheme()">☾</button>
</header>

<div class="container">
  <div id="hero-slot">{hero_html}</div>
  <div class="section-head"><h2>Latest Dispatches</h2></div>
  <div class="list" id="news-list">{list_html}</div>
</div>

<footer>
  <p><span class="foot-brand">TejalTechWire</span> — Independent AI, Tech &amp; Gadget news desk. &copy; 2026.</p>
  <p><a href="/about.html">About</a>|<a href="/contact.html">Contact</a>|<a href="/privacy.html">Privacy Policy</a></p>
</footer>

<script type="application/json" id="articles-data">{articles_json}</script>
<script>
  const themeBtn = document.getElementById('themeBtn');
  let currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';

  function toggleTheme(){{
    currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
    themeBtn.innerText = currentTheme === 'dark' ? '☀' : '☾';
  }}

  const CAT_CLASS = {{'AI':'ai', 'Tech':'tech', 'Gadgets':'gadgets', 'Mobile':'mobile', 'Business':'business'}};
  // Page load hote hi content pehle se HTML mein maujood hai (SEO ke liye).
  // Ye embedded data sirf CATEGORY FILTER buttons ke liye use hota hai — koi extra network call nahi.
  const allArticles = JSON.parse(document.getElementById('articles-data').textContent);

  function timeAgo(iso){{
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs/60000);
    if(mins < 60) return mins + 'm ago';
    const hrs = Math.floor(mins/60);
    if(hrs < 24) return hrs + 'h ago';
    return Math.floor(hrs/24) + 'd ago';
  }}

  function escapeHtml(str){{
    const d = document.createElement('div');
    d.innerText = str || '';
    return d.innerHTML;
  }}

  function initials(name){{
    if(!name) return 'TW';
    const parts = name.replace('TejalTechWire','TW').split(' ');
    return parts.slice(0,2).map(p => p[0]).join('').toUpperCase().slice(0,2);
  }}

  function renderNews(articles){{
    const heroSlot = document.getElementById('hero-slot');
    const list = document.getElementById('news-list');

    if(!articles.length){{
      heroSlot.innerHTML = '';
      list.innerHTML = '<div class="empty-state">// No dispatches in this category yet.</div>';
      return;
    }}

    const [top, ...rest] = articles;
    const topCls = CAT_CLASS[top.category] || 'gadgets';
    heroSlot.innerHTML = `
      <a class="hero" href="/articles/${{top.url_path}}.html">
        <img src="${{top.image_url || 'https://via.placeholder.com/700x400?text=TejalTechWire'}}" alt="">
        <div class="hero-body">
          <span class="cat-badge ${{topCls}}">${{escapeHtml(top.category)}}</span>
          <h1>${{escapeHtml(top.title)}}</h1>
          <div class="byline">
            <div class="avatar">${{initials(top.source_name)}}</div>
            <div class="byline-text">${{escapeHtml(top.source_name)}} · ${{timeAgo(top.published_at)}}</div>
          </div>
        </div>
      </a>`;

    list.innerHTML = rest.map(a => {{
      const cls = CAT_CLASS[a.category] || 'gadgets';
      return `
        <a class="row" href="/articles/${{a.url_path}}.html">
          <div class="row-body">
            <span class="row-cat ${{cls}}">${{escapeHtml(a.category)}}</span>
            <h3>${{escapeHtml(a.title)}}</h3>
            <span class="row-time">${{timeAgo(a.published_at)}}</span>
          </div>
          <img src="${{a.image_url || 'https://via.placeholder.com/160x160?text=TW'}}" alt="">
        </a>`;
    }}).join('');
  }}

  function filterNews(category, btn){{
    document.querySelectorAll('#nav-filters .pill').forEach(p => p.classList.remove('active'));
    if(btn) btn.classList.add('active');
    if(category === 'All'){{
      renderNews(allArticles);
    }}else{{
      renderNews(allArticles.filter(a => a.category === category));
    }}
  }}
</script>
</body>
</html>
"""


def _trending_badge(a):
    """Badge hata diya gaya — sabhi published news pehle se hi trending-filtered hain
    (threshold pass kiye bina publish hoti hi nahi), isliye alag se badge dikhana zaroori nahi.
    trending_score internally filtering ke liye abhi bhi use hota hai."""
    return ""



def _render_hero_html(a):
    cls = CAT_CLASS_MAP.get(a.get("category"), "gadgets")
    image = a.get("image_url") or "https://via.placeholder.com/700x400?text=TejalTechWire"
    source_name = a.get("source_name") or "TejalTechWire Original"
    return f"""<a class="hero" href="/articles/{article_url_path(a['id'], a.get('title',''))}.html">
        <img src="{image}" alt="{_escape_html(a.get('title',''))}">
        <div class="hero-body">
          <span class="cat-badge {cls}">{_escape_html(a.get('category',''))}</span>
          {_trending_badge(a)}
          <h1>{_escape_html(a.get('title',''))}</h1>
          <div class="byline">
            <div class="avatar">{_initials(source_name)}</div>
            <div class="byline-text">{_escape_html(source_name)} · {_time_ago(a.get('published_at',''))}</div>
          </div>
        </div>
      </a>"""


def _render_row_html(a):
    cls = CAT_CLASS_MAP.get(a.get("category"), "gadgets")
    image = a.get("image_url") or "https://via.placeholder.com/160x160?text=TW"
    return f"""<a class="row" href="/articles/{article_url_path(a['id'], a.get('title',''))}.html">
          <div class="row-body">
            <span class="row-cat {cls}">{_escape_html(a.get('category',''))}</span>
            {_trending_badge(a)}
            <h3>{_escape_html(a.get('title',''))}</h3>
            <span class="row-time">{_time_ago(a.get('published_at',''))}</span>
          </div>
          <img src="{image}" alt="{_escape_html(a.get('title',''))}">
        </a>"""


def generate_homepage(conn):
    """Homepage ko fetcher.py hi generate karta hai — content pehle se HTML mein hota hai,
    JS sirf category-filter buttons ke liye use hota hai. Crawlers ko turant content milta hai."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published_at DESC LIMIT 30")
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r["url_path"] = article_url_path(r["id"], r.get("title", ""))   # JS filter ke liye

    if not rows:
        hero_html = ""
        list_html = '<div class="empty-state">// No dispatches yet — waiting for the next automated update cycle...</div>'
    else:
        top, rest = rows[0], rows[1:]
        hero_html = _render_hero_html(top)
        list_html = "".join(_render_row_html(a) for a in rest)

    html = HOME_TEMPLATE.format(
        site_url=SITE_URL,
        hero_html=hero_html,
        list_html=list_html,
        articles_json=json.dumps(rows),
    )
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Homepage (index.html) regenerated with pre-rendered content")


def _github_new_file_link(path, content):
    """GitHub ka special URL jo ek 'naya file banao' page kholta hai, content pehle se
    bhara hua — user ko sirf 'Commit new file' dabana hota hai, kuch type nahi karna padta."""
    from urllib.parse import quote
    return f"https://github.com/{GITHUB_REPO}/new/{GITHUB_BRANCH}?filename={quote(path)}&value={quote(content)}"


def _github_edit_link(path):
    """Kisi existing file ko seedha GitHub par edit karne ka link."""
    return f"https://github.com/{GITHUB_REPO}/edit/{GITHUB_BRANCH}/{path}"


def generate_review_page(conn):
    """Draft Review System: sabhi pending drafts ko ek page par dikhata hai jahan tum
    poora article padh sakte ho, aur Approve / Reject / Edit kar sakte ho — bina kisi
    login/backend ke, seedha GitHub ke through."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM drafts ORDER BY created_at DESC")
    drafts = [dict(r) for r in cursor.fetchall()]

    os.makedirs("review", exist_ok=True)

    if not drafts:
        cards_html = '<div class="empty-state">// Koi pending draft nahi hai abhi. Agla workflow run naye drafts la sakta hai.</div>'
    else:
        cards = []
        for d in drafts:
            approve_link = _github_new_file_link(f"approvals/approve_{d['id']}.txt", "approve")
            reject_link = _github_new_file_link(f"approvals/reject_{d['id']}.txt", "reject")
            edit_link = _github_edit_link(f"drafts_text/{d['id']}.txt")
            cls = CAT_CLASS_MAP.get(d.get("category"), "gadgets")
            cards.append(f"""
            <div class="draft-card">
              <img src="{d.get('image_url','')}" alt="">
              <div class="draft-body">
                <span class="cat-badge {cls}">{_escape_html(d.get('category',''))}</span>
                {_trending_badge(d)}
                <h2>{_escape_html(d.get('title',''))}</h2>
                <div class="draft-text">{_paragraphs_html(d.get('summary',''))}</div>
                <div class="draft-actions">
                  <a class="btn-approve" href="{approve_link}" target="_blank">✅ Approve &amp; Publish</a>
                  <a class="btn-edit" href="{edit_link}" target="_blank">✏️ Edit Text</a>
                  <a class="btn-reject" href="{reject_link}" target="_blank">🗑️ Reject</a>
                </div>
                <p class="draft-hint">Approve/Reject click karne ke baad GitHub khulega — wahan "Commit new file" dabao. Agle workflow run (30 min tak) mein ye process ho jaayega.</p>
              </div>
            </div>""")
        cards_html = "".join(cards)

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Draft Review — TejalTechWire (Private)</title>
<meta name="robots" content="noindex, nofollow">
<link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
<style>
  .draft-card{{background:var(--panel); border:1px solid var(--line); border-radius:10px; overflow:hidden; margin-bottom:1.5rem; box-shadow:var(--shadow);}}
  .draft-card img{{width:100%; height:220px; object-fit:cover;}}
  .draft-body{{padding:1.3rem;}}
  .draft-body h2{{font-family:'Space Grotesk'; font-size:1.3rem; margin:.8rem 0;}}
  .draft-text p{{font-size:.95rem; line-height:1.6; color:var(--text-dim); margin:0 0 .8rem;}}
  .draft-actions{{display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1rem;}}
  .draft-actions a{{
    font-family:'Space Grotesk'; font-weight:700; font-size:.85rem; padding:.6rem 1.1rem;
    border-radius:6px; text-decoration:none; display:inline-block;
  }}
  .btn-approve{{background:#33D6A6; color:#0A0A0C;}}
  .btn-edit{{background:var(--accent); color:#0A0A0C;}}
  .btn-reject{{background:transparent; color:#FF5D6C; border:1px solid #FF5D6C;}}
  .draft-hint{{font-family:'IBM Plex Mono'; font-size:.72rem; color:var(--text-dim); margin-top:.8rem;}}
</style>
</head>
<body>
<header>
  <a class="logo" href="/">
    <div class="logo-mark">TW</div>
    <div class="logo-text">Tejal<span>Tech</span>Wire</div>
  </a>
</header>
<div class="container">
  <h1 style="font-family:'Space Grotesk'; margin-bottom:.3rem;">📝 Draft Review</h1>
  <p style="color:var(--text-dim); font-family:'IBM Plex Mono'; font-size:.8rem; margin-bottom:2rem;">Private page — {len(drafts)} pending draft(s)</p>
  {cards_html}
</div>
</body>
</html>
"""
    with open("review/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Review page generated with {len(drafts)} pending draft(s)")


def generate_article_pages(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles ORDER BY published_at DESC")
    rows = [dict(r) for r in cursor.fetchall()]

    os.makedirs("articles", exist_ok=True)

    for a in rows:
        image = a.get("image_url") or FALLBACK_IMAGES.get(a.get("category"), "")
        description = _escape_html(_plain_summary(a.get("summary"), 160))
        cat_class = CAT_CLASS_MAP.get(a.get("category"), "gadgets")
        source_name = a.get("source_name") or "TejalTechWire Original"
        url_path = article_url_path(a["id"], a.get("title", ""))

        # --- isی category ke 3 aur articles dhoondh ke "Related" links banate hain ---
        related = [r for r in rows if r.get("category") == a.get("category") and r["id"] != a["id"]][:3]
        if related:
            related_html = "".join(
                f'<a class="related-item" href="/articles/{article_url_path(r["id"], r.get("title",""))}.html">'
                f'<img src="{r.get("image_url") or FALLBACK_IMAGES.get(r.get("category"), "")}" alt="">'
                f'<h4>{_escape_html(r.get("title", ""))}</h4></a>'
                for r in related
            )
        else:
            related_html = '<p style="color:var(--text-dim); font-size:.9rem;">More stories coming soon.</p>'

        # Structured data (JSON-LD) ke andar safely daalne ke liye JSON-escaped strings
        title_json = json.dumps(a.get("title", ""))
        description_json = json.dumps(_plain_summary(a.get("summary"), 200))
        image_json = json.dumps(image)
        try:
            date_iso = datetime.fromisoformat(a.get("published_at", "")).strftime('%Y-%m-%dT%H:%M:%S+00:00')
        except Exception:
            date_iso = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')

        html = ARTICLE_TEMPLATE.format(
            title=_escape_html(a.get("title", "")),
            description=description,
            image=image,
            url=f"{SITE_URL}/articles/{url_path}.html",
            cat_class=cat_class,
            category=_escape_html(a.get("category", "")),
            trending_badge=_trending_badge(a),
            avatar=_initials(source_name),
            source_name=_escape_html(source_name),
            time_str=_time_ago(a.get("published_at", "")),
            body_html=_paragraphs_html(a.get("summary", "")),
            related_html=related_html,
            title_json=title_json,
            description_json=description_json,
            image_json=image_json,
            date_iso=date_iso,
            site_url=SITE_URL,
        )

        with open(f"articles/{url_path}.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Purana format (/articles/<id>.html) agar kahin already share/index ho chuka ho,
        # to wahan ek simple redirect chhod dete hain taaki koi link na toote.
        redirect_html = (
            f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
            f'<meta http-equiv="refresh" content="0; url=/articles/{url_path}.html">'
            f'<link rel="canonical" href="{SITE_URL}/articles/{url_path}.html">'
            f'</head><body>Redirecting... <a href="/articles/{url_path}.html">Click here</a></body></html>'
        )
        with open(f"articles/{a['id']}.html", "w", encoding="utf-8") as f:
            f.write(redirect_html)

    print(f"Generated {len(rows)} article pages in /articles/")
    return rows


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    if os.path.exists('schema.sql'):
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())
    # Safe migration: agar purani DB mein trending_score column nahi hai to add kar do
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN trending_score REAL DEFAULT 0")
        conn.commit()
        print("Migrated: added trending_score column to existing database")
    except sqlite3.OperationalError:
        pass  # column already exists
    return conn


def fetch_full_article(url):
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
        if resp.status_code != 200 or not resp.text:
            print(f"Fetch failed ({resp.status_code}) for {url}")
            return None
        text = trafilatura.extract(resp.text)
        return text
    except Exception as e:
        print(f"Full article fetch failed for {url}: {e}")
        return None


# --- FIX: ab "seen_urls" leta hai — jo links pehle publish ho chuke hain unhe SKIP karke
# feed ke AGE ke entries check karta rehta hai, poori category chhodta nahi ---
def get_latest_entry_with_text(feed_url, seen_urls):
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        print(f"Feed parse failed for {feed_url}: {e}")
        return None
    if not feed.entries:
        print(f"No entries found in feed: {feed_url}")
        return None
    for entry in feed.entries[:10]:
        link = entry.get("link")
        if not link:
            continue
        if link in seen_urls:
            print(f"  (already published before, trying next entry): {link}")
            continue
        text = fetch_full_article(link)
        if text and len(text) > 200:
            return {"title": entry.get("title", ""), "text": text[:4000], "link": link}
    return None


def get_two_articles(feed_urls, seen_urls):
    collected = []
    for feed_url in feed_urls:
        print(f"Trying source: {feed_url}")
        entry = get_latest_entry_with_text(feed_url, seen_urls)
        if entry:
            collected.append(entry)
            print(f"  -> Got: {entry['title'][:60]}")
        else:
            print(f"  -> Failed/empty/all-repeated: {feed_url}")
        if len(collected) >= 2:
            break
    return collected


def _build_source_blocks(sources):
    blocks = []
    for i, s in enumerate(sources):
        label = "SOURCE A" if i == 0 else "SOURCE B"
        blocks.append(f'''--- {label}: "{s["title"]}" ---
{s["text"]}''')
    return "\n\n".join(blocks)


def _call_gemini_once(sources, category, target_keywords):
    """Gemini ko ek baar call karta hai. sources ek list hai -- 2 ho sakti hain (dono
    genuinely related ho tab) ya sirf 1 (jab dusra source topic se match nahi karta,
    isliye jabardasti mix nahi karte). Fail hone par exception raise karta hai."""
    source_blocks = _build_source_blocks(sources)
    combine_instruction = (
        "Read both carefully, then write a brand-new, completely original article in your own words "
        "-- combining the key facts, context, and angles from both. Do NOT copy any sentence or "
        "phrasing from the sources."
        if len(sources) > 1 else
        "Read it carefully, then write a brand-new, completely original article in your own words "
        "based on it. Do NOT copy any sentence or phrasing from the source."
    )
    source_word = "sources" if len(sources) > 1 else "source"

    prompt = f'''
        You are a friendly tech writer for \'TejalTechWire\', explaining recent developments in
        AI, Technology, and Gadgets to EVERYDAY READERS in the US and UK who are not tech experts.

        Below {"are" if len(sources) > 1 else "is"} {len(sources)} full source article{"s" if len(sources) > 1 else ""}
        on recent development{"s" if len(sources) > 1 else ""} in the \'{category}\' space.
        {combine_instruction}

        AUDIENCE: Write for a general American and British audience. Use US/UK spelling and phrasing.
        Prices should stay in the currency mentioned in the {source_word} (usually USD "$"); if converting,
        prefer USD. Do not add India-specific or any other region-specific framing or comparisons unless
        the source material itself is about that region.

        SEO KEYWORDS -- this is important: These are the real, specific keywords tied to this story
        that people are likely to actually search for (extracted from the source headlines): {target_keywords}.
        Naturally include the 1-2 MOST relevant/specific of these (e.g. product name + the key action --
        "launch", "price", "release date", "review") in your TITLE and again once early in the article.
        Do this naturally, like a real headline would -- NEVER force in all of them, NEVER keyword-stuff.

        SEARCH INTENT -- this is important: Think about what someone searching Google for this topic
        actually wants to know (e.g. price, release date, availability, what it does, how it compares).
        If the {source_word} contain that specific information, make sure your article directly and
        clearly states it -- do not just vaguely gesture at "details" when a concrete fact is available.

        WRITING STYLE:
        - Use SIMPLE, PLAIN language, like explaining to a smart friend who doesn't follow tech news.
        - Short sentences. One idea per sentence where possible.
        - Explain any technical term/jargon in plain words the moment you use it.
        - ALWAYS write numbers and years as normal digits (e.g. "2028", "7.5 billion", "$500") --
          NEVER spell them out as words.
        - Avoid heavy, literary words like "amid", "underscores", "harbinger".

        ARTICLE STRUCTURE -- follow this EXACT plain-text format (no markdown symbols like ** or #):
        1. Start with 1-2 opening paragraphs (no heading) that clearly state what happened and why
           it matters -- in plain, simple language.
        2. Then add 2-3 short sections, each starting on its own line with exactly:
           HEADING: <short section title, e.g. "What This Means" or "Price and Availability">
           followed by 1 short paragraph for that section.
        3. End with a section starting with exactly:
           HEADING: Quick Questions Answered
           followed by 2-3 question/answer pairs, each formatted as TWO separate lines:
           Q: <a short, natural question someone might search for>
           A: <a short, direct, factual answer based on the source material>
        Leave one blank line between every paragraph/heading/Q-A block.

        {source_blocks}

        Also suggest a short stock-photo search phrase (2-4 words) that visually captures the SPECIFIC
        subject of THIS article (not people's names or brand names) for a royalty-free stock photo search.

        Format your FULL response strictly as:
        TITLE: [Your new original catchy headline, in simple plain language]
        CONTENT: [Your full article following the ARTICLE STRUCTURE above]
        IMAGE_KEYWORDS: [2-4 word generic visual search phrase]
        '''

    response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
    text = response.text.strip()
    image_keywords = category.lower()

    if "IMAGE_KEYWORDS:" in text:
        text, keyword_part = text.split("IMAGE_KEYWORDS:", 1)
        image_keywords = keyword_part.strip().strip('"').strip() or image_keywords

    if "TITLE:" not in text or "CONTENT:" not in text:
        raise ValueError("Gemini response missing TITLE:/CONTENT: markers")

    parts = text.split("CONTENT:")
    new_title = parts[0].replace("TITLE:", "").strip()
    new_content = parts[1].strip()

    if not new_title or not new_content or len(new_content) < 100:
        raise ValueError("Gemini response too short/empty")

    return new_content, new_title, image_keywords


def generate_merged_article(sources, category, target_keywords=""):
    """Gemini se article generate karta hai. sources = list of 1 ya 2 source dicts.
    Fail hone par 1 baar retry karta hai. Dono attempts fail hon to (None, None, None)
    return karta hai -- fetch_and_process is category ko SKIP kar deta hai."""
    if not client:
        print("Gemini client not configured (missing GEMINI_API_KEY) -- skipping this category")
        return None, None, None

    for attempt in (1, 2):
        try:
            return _call_gemini_once(sources, category, target_keywords)
        except Exception as e:
            print(f"Gemini generation attempt {attempt} failed: {e}")
            if attempt == 2:
                print("Both attempts failed -- skipping this category this run (no placeholder published)")
                return None, None, None


def fetch_and_process(conn):
    cursor = conn.cursor()
    os.makedirs("data", exist_ok=True)
    # (publishing ab yahan se nahi hoti, drafts mein jaata hai — process_approvals() publish karta hai)

    # pehle "used_source_links" table se (ye dono A aur B links record karti hai),
    # aur purane data ke liye "articles.source_url" se bhi -- dono jagah se "already used" list banate hain.
    cursor.execute("SELECT link FROM used_source_links")
    seen_urls = {row[0] for row in cursor.fetchall()}
    cursor.execute("SELECT source_url FROM articles WHERE source_url IS NOT NULL")
    seen_urls |= {row[0] for row in cursor.fetchall() if row[0] and row[0] != "#"}
    print(f"Already-used source links tracked: {len(seen_urls)}")

    # NAYA: trending detection ke liye saari feeds ka snapshot ek hi baar le lete hain
    print("\nFetching all feed titles for trending/overlap analysis...")
    titles_by_feed = get_all_recent_titles()
    print(f"Collected {len(titles_by_feed)} recent titles across all sources for comparison")

    for category, feed_urls in SOURCES.items():
        print(f"\n=== Processing category: {category} ===")
        articles = get_two_articles(feed_urls, seen_urls)

        if len(articles) < 2:
            print(f"Skipping {category}: only got {len(articles)}/2 fresh valid sources after trying all candidates")
            continue

        article_a, article_b = articles[0], articles[1]
        link_a = article_a.get("link", "")
        link_b = article_b.get("link", "")

        # NAYA: TRENDING CHECK -- Gemini ko call karne se PEHLE hi decide kar lete hain
        # ki kya ye story genuinely trending/viral hai. Agar nahi, publish hi nahi karte
        # (na hi Gemini API waste hoti hai) -- sirf "kachra" filter ho jaata hai.
        print(f"Checking trending score for: {article_a['title'][:70]}")
        trending_score = compute_trending_score(article_a["title"], titles_by_feed)

        # NAYA: yehi keywords ab Gemini ko bhi diye jaate hain, taaki title/article mein
        # genuinely search hone waale terms naturally shamil hon (sirf trending-check ke
        # liye internal use na ho kar reh jaayein).
        story_keywords = ", ".join(sorted(_keywords(article_a["title"]) | _keywords(article_b["title"])))

        # NAYA: "do alag news mix na ho" fix -- agar A aur B genuinely unrelated stories
        # hain (jaise "Apple headset" + "drone ban"), to inhe jabardasti ek article mein
        # nahi milaate. Sirf jo zyaada trending/relevant hai (article_a) usi se article banta hai.
        if are_related(article_a["title"], article_b["title"]):
            sources_for_article = [article_a, article_b]
            print("Sources are related -- merging both into one article")
        else:
            sources_for_article = [article_a]
            print("Sources are UNRELATED -- using only the primary source, not mixing two different stories")

        # Dono links turant lock kar dete hain -- chahe story trending nikle ya na nikle,
        # ye 2 source articles is run mein "consume" ho chuke hain, dobara kisi aur category
        # mein use nahi honge. Isi se "same story 3-4 baar chapna" wala bug bhi fix hota hai.
        for link in (link_a, link_b):
            if link:
                cursor.execute(
                    "INSERT OR IGNORE INTO used_source_links (link, used_at) VALUES (?, ?)",
                    (link, datetime.now().isoformat())
                )
                seen_urls.add(link)
        conn.commit()

        if trending_score < MIN_TRENDING_SCORE:
            print(f"Skipping {category}: trending score {trending_score} is below threshold {MIN_TRENDING_SCORE} -- not viral/important enough")
            continue

        print(f"Trending score {trending_score} >= {MIN_TRENDING_SCORE} -- proceeding to generate article")
        print(f"Generating {category} article with Gemini (target keywords: {story_keywords})...")
        summary, title, image_keywords = generate_merged_article(sources_for_article, category, story_keywords)

        # Gemini fail ho gaya (dono retries) -- is category ko is run mein publish
        # hi mat karo. Placeholder/khali article site par nahi jaana chahiye.
        if not summary or not title:
            print(f"Skipping {category}: article generation failed, nothing published this run")
            continue

        image_url = get_stock_image(image_keywords, category)

        cursor.execute("SELECT id FROM articles WHERE title = ?", (title,))
        if cursor.fetchone():
            print(f"Duplicate title skipped: {title}")
            continue
        cursor.execute("SELECT id FROM drafts WHERE title = ?", (title,))
        if cursor.fetchone():
            print(f"Duplicate title (already in drafts) skipped: {title}")
            continue

        # --- NAYA: seedhe 'articles' (live site) mein NAHI jaata — pehle 'drafts' mein
        # jaata hai, review page par dikhega, tumhare Approve karne ke baad hi publish hoga. ---
        cursor.execute("""
            INSERT INTO drafts (title, summary, category, image_url, source_name, source_url, trending_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, summary, category, image_url, "TejalTechWire Original", link_a, trending_score, datetime.now().isoformat()))
        draft_id = cursor.lastrowid

        # Draft ka text ek alag file mein bhi save karte hain, taaki tum chaho to
        # GitHub par seedha edit kar sako publish hone se pehle.
        os.makedirs("drafts_text", exist_ok=True)
        with open(f"drafts_text/{draft_id}.txt", "w", encoding="utf-8") as f:
            f.write(f"TITLE: {title}\n\nCONTENT:\n{summary}")

        print(f"Added to DRAFTS for review (score={trending_score}): {title}")

    conn.commit()
    return []   # publish yahan se nahi hota — process_approvals() publish karta hai


# --- NAYA: Approve/Reject system. GitHub mein banayi gayi "approvals/" files ko check karta
# hai. Tum review page se ek link click karte ho, GitHub khulta hai, tum "Commit" dabate ho
# -- agli baar workflow chalne par ye function wahi dekh kar publish/reject karta hai. ---
def process_approvals(conn):
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    newly_published_ids = []

    if not os.path.isdir("approvals"):
        return newly_published_ids

    for fname in os.listdir("approvals"):
        fpath = os.path.join("approvals", fname)
        if not fname.endswith(".txt"):
            continue

        if fname.startswith("approve_"):
            draft_id = fname.replace("approve_", "").replace(".txt", "")
            cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()
            if row:
                d = dict(row)

                # Agar tumne drafts_text/<id>.txt file edit ki thi, wahi final content use hota hai
                title, summary = d["title"], d["summary"]
                text_path = f"drafts_text/{draft_id}.txt"
                if os.path.exists(text_path):
                    with open(text_path, "r", encoding="utf-8") as f:
                        edited = f.read()
                    if "TITLE:" in edited and "CONTENT:" in edited:
                        parts = edited.split("CONTENT:")
                        edited_title = parts[0].replace("TITLE:", "").strip()
                        edited_content = parts[1].strip()
                        if edited_title:
                            title = edited_title
                        if edited_content:
                            summary = edited_content

                cursor.execute("""
                    INSERT INTO articles (title, summary, category, image_url, source_name, source_url, published_at, trending_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (title, summary, d["category"], d["image_url"], d["source_name"], d["source_url"],
                      datetime.now().isoformat(), d["trending_score"]))
                newly_published_ids.append(cursor.lastrowid)
                print(f"APPROVED and published draft {draft_id}: {title}")

                cursor.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
                if os.path.exists(text_path):
                    os.remove(text_path)
            os.remove(fpath)

        elif fname.startswith("reject_"):
            draft_id = fname.replace("reject_", "").replace(".txt", "")
            cursor.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            text_path = f"drafts_text/{draft_id}.txt"
            if os.path.exists(text_path):
                os.remove(text_path)
            print(f"REJECTED draft {draft_id}, deleted")
            os.remove(fpath)

    conn.commit()
    return newly_published_ids


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
    <loc>{SITE_URL}/articles/{article_url_path(a['id'], a.get('title',''))}.html</loc>
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
    print(f"sitemap.xml generated with {len(url_entries)} URLs!")


def generate_robots_txt():
    content = f"""User-agent: *
Allow: /
Disallow: /review/
Disallow: /drafts_text/
Disallow: /approvals/

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(content)
    print("robots.txt generated!")


if __name__ == "__main__":
    print("Starting TejalTechWire Autonomous Content Engine...")
    db_conn = setup_db()

    # 1) Pehle dekh lete hain — kya pichle cycle mein tumne kisi draft ko GitHub par
    # Approve/Reject kiya tha? Agar haan, to yahan wo process hota hai (publish/delete).
    approved_ids = process_approvals(db_conn)

    # 2) Naye stories dhoondo, trending-filter lagao, "drafts" mein daalo (LIVE nahi hota)
    fetch_and_process(db_conn)

    export_to_json(db_conn)
    all_rows = generate_article_pages(db_conn)
    generate_homepage(db_conn)
    generate_review_page(db_conn)   # <-- NAYA: draft review page banti hai
    generate_sitemap(all_rows)
    generate_robots_txt()
    generate_indexnow_key_file()

    # --- naye APPROVED-and-published articles ke baare mein Bing/Yandex ko turant bata dete hain ---
    new_urls = []
    if approved_ids:
        conn2 = db_conn
        conn2.row_factory = sqlite3.Row
        c2 = conn2.cursor()
        for aid in approved_ids:
            c2.execute("SELECT id, title FROM articles WHERE id = ?", (aid,))
            r = c2.fetchone()
            if r:
                new_urls.append(f"{SITE_URL}/articles/{article_url_path(r['id'], r['title'])}.html")
    if new_urls:
        submit_indexnow([f"{SITE_URL}/"] + new_urls)
    else:
        print("No newly-approved articles this run — skipping IndexNow submission")

    db_conn.close()
    print("Generation Complete!")
