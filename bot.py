import os, requests, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from dateutil import parser
import pytz

# Load Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# The Upgraded Pro-Trader Feeds
FEEDS = [
    'https://finance.yahoo.com/news/rss',
    'https://www.fxstreet.com/rss/news',              # High-tier currency pairs
    'https://www.forexlive.com/feed',                 # Essential for MT4/FXCM scalpers
    'https://www.myfxbook.com/rss/latest-forex-news'  # Myfxbook community news
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})

def analyze_and_send():
    now_utc = datetime.now(timezone.utc)
    # FOR TESTING: Looking at the last 2 days so we guarantee a message triggers right now!
    time_limit = now_utc - timedelta(days=2) 
    bd_timezone = pytz.timezone('Asia/Dhaka')

    # The "Fake Mustache" - This makes us look like a standard web browser
    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    for url in FEEDS:
        try:
            # We pass the fake headers to bypass the scraper block
            response = requests.get(url, headers=request_headers, timeout=10)
            
            # If the website still blocks us (Status code 403 or 404), skip it safely without crashing
            if response.status_code != 200:
                print(f"Blocked by {url} - Status Code: {response.status_code}")
                continue

            root = ET.fromstring(response.content)
            
            # FXLive and some others use a namespace, so we search broadly for items
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else "No Title"
                desc = item.find('description').text if item.find('description') is not None else "No summary."
                pub_date_node = item.find('pubDate')
                
                # Skip if there's no published date
                if pub_date_node is None:
                    continue
                    
                pub_date_str = pub_date_node.text
                
                # Parse date and ensure it's timezone aware
                try:
                    pub_date = parser.parse(pub_date_str)
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                except:
                    continue

                # If the article is brand new, process it
                if pub_date > time_limit:
                    prompt = f"""You are an expert financial quant. Analyze this breaking news:
                    Headline: {title}
                    Summary: {desc}
                    Return ONLY a raw JSON object with these 3 keys:
                    "Asset" (The specific ticker symbol or "Macro"),
                    "Sentiment" ("Bullish", "Bearish", or "Neutral"),
                    "Analysis" (One short, punchy sentence explaining the market impact)."""

                    payload = {"contents": [{ "parts": [{"text": prompt}] }]}
                    gemini_headers = {"Content-Type": "application/json"}
                    
                    # THE FIX: Pointing to the new, active Gemini API endpoint
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
                    
                    ai_response = requests.post(api_url, headers=gemini_headers, json=payload)
                    
                    # Safe check if Gemini API fails
                    if ai_response.status_code != 200:
                        print(f"Gemini API Error: {ai_response.status_code}")
                        continue
                        
                    ai_data = ai_response.json()
                    
                    # Clean and parse JSON response
                    raw_text = ai_data['candidates'][0]['content']['parts'][0]['text']
                    clean_json = raw_text.replace('```json', '').replace('```', '').strip()
                    analysis = json.loads(clean_json)

                    # Format Time for Bangladesh
                    local_time = now_utc.astimezone(bd_timezone).strftime('%I:%M %p')

                    # Format Telegram Message
                    msg = (
                        f"🚨 <b>COSMIC TRADER ALERT</b> 🚨\n"
                        f"🕒 {local_time} (BST)\n\n"
                        f"📰 <b>News:</b> {title}\n"
                        f"📈 <b>Asset:</b> {analysis['Asset']}\n"
                        f"📊 <b>Sentiment:</b> {analysis['Sentiment']}\n\n"
                        f"🧠 <b>AI Analysis:</b> {analysis['Analysis']}"
                    )
                    
                    send_telegram(msg)
                    print(f"Sent alert for: {title}")
                    
        except Exception as e:
            print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    analyze_and_send()
