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
# Notice the '#' in front of Yahoo. This temporarily turns it off, 
# making it incredibly easy for you to turn back on in the future!
FEEDS = [
    # 'https://finance.yahoo.com/news/rss',  
    'https://www.fxstreet.com/rss/news',
    'https://www.forexlive.com/feed',
    'https://www.myfxbook.com/rss/latest-forex-news'
]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"})

def analyze_and_send():
    now_utc = datetime.now(timezone.utc)
    time_limit = now_utc - timedelta(minutes=6) # Set to Live Mode
    bd_timezone = pytz.timezone('Asia/Dhaka')

    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }

    for url in FEEDS:
        try:
            response = requests.get(url, headers=request_headers, timeout=10)
            
            if response.status_code != 200:
                continue

            root = ET.fromstring(response.content)
            
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else "No Title"
                desc = item.find('description').text if item.find('description') is not None else "No summary."
                pub_date_node = item.find('pubDate')
                
                if pub_date_node is None:
                    continue
                    
                pub_date_str = pub_date_node.text
                
                try:
                    pub_date = parser.parse(pub_date_str)
                    if pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                except:
                    continue

                if pub_date > time_limit:
                    # THE NEW FOREX-ONLY PROMPT
                    prompt = f"""You are an expert Forex quant trader. Analyze this breaking news:
                    Headline: {title}
                    Summary: {desc}
                    
                    CRITICAL INSTRUCTION: If this news is ONLY about a specific company stock (e.g., Apple earnings, Tesla sales) and has no major impact on currency pairs or macro-economics, return EXACTLY this JSON: {{"Skip": true}}
                    
                    Otherwise, return ONLY a raw JSON object with these 4 keys:
                    "Asset" (The specific currency pair like EUR/USD, GBP/JPY, or "Macro/USD"),
                    "Sentiment" ("Bullish", "Bearish", or "Neutral"),
                    "Scalp_Analysis" (One short sentence on the immediate 1-to-15 minute Forex market reaction),
                    "Swing_Analysis" (One short sentence on the broader 1-week to 1-month Forex trend impact)."""

                    payload = {"contents": [{ "parts": [{"text": prompt}] }]}
                    gemini_headers = {"Content-Type": "application/json"}
                    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
                    
                    ai_response = requests.post(api_url, headers=gemini_headers, json=payload)
                    
                    if ai_response.status_code != 200:
                        continue
                        
                    ai_data = ai_response.json()
                    
                    raw_text = ai_data['candidates'][0]['content']['parts'][0]['text']
                    clean_json = raw_text.replace('```json', '').replace('```', '').strip()
                    analysis = json.loads(clean_json)

                    # THE KILL SWITCH: If Gemini says it's a stock, silently ignore it
                    if analysis.get("Skip") is True:
                        print(f"Ignored Stock News: {title}")
                        continue

                    local_time = now_utc.astimezone(bd_timezone).strftime('%I:%M %p')

                    msg = (
                        f"🚨 <b>COSMIC TRADER ALERT</b> 🚨\n"
                        f"🕒 {local_time} (BST)\n\n"
                        f"📰 <b>News:</b> {title}\n"
                        f"📈 <b>Asset:</b> {analysis['Asset']}\n"
                        f"📊 <b>Sentiment:</b> {analysis['Sentiment']}\n\n"
                        f"⚡ <b>Scalp:</b> {analysis['Scalp_Analysis']}\n\n"
                        f"🌊 <b>Swing:</b> {analysis['Swing_Analysis']}"
                    )
                    
                    send_telegram(msg)
                    print(f"Sent alert for: {title}")
                    
        except Exception as e:
            print(f"Error processing {url}: {e}")

if __name__ == "__main__":
    analyze_and_send()
