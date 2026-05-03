import os, requests, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from dateutil import parser
import pytz

# Load Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# The Feeds
FEEDS = [
    'https://finance.yahoo.com/news/rss',
    'https://www.fxstreet.com/rss/news',
    'https://investinglive.com/rss/news'
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})

def analyze_and_send():
    now_utc = datetime.now(timezone.utc)
    time_limit = now_utc - timedelta(minutes=6) # Look for news from the last 6 minutes
    bd_timezone = pytz.timezone('Asia/Dhaka')

    for url in FEEDS:
        try:
            response = requests.get(url, timeout=10)
            root = ET.fromstring(response.content)
            
            for item in root.findall('.//item'):
                title = item.find('title').text
                desc = item.find('description').text if item.find('description') is not None else "No summary."
                pub_date_str = item.find('pubDate').text
                
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
                    headers = {"Content-Type": "application/json"}
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                    
                    ai_response = requests.post(api_url, headers=headers, json=payload)
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
                    
        except Exception as e:
            print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    analyze_and_send()
