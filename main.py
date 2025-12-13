import requests
import pandas as pd
import datetime
import time
import os
import xml.etree.ElementTree as ET
import argparse
import random
import sys

# --- CONFIGURATION ---
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Public Mirrors to bypass AWS/Data Center IP Blocks
# old.reddit.com works from residential IPs, mirrors for data centers
MIRRORS = [
    "https://old.reddit.com",
    "https://redlib.catsarch.com",
    "https://redlib.vsls.cz",
    "https://r.nf",
    "https://libreddit.northboot.xyz",
    "https://redlib.tux.pizza"
]

SEEN_URLS = set()

def get_file_path(target, type_prefix):
    """Generates a dynamic filename (e.g., data/r_python.csv or data/u_elonmusk.csv)"""
    # Ensure data directory exists
    if not os.path.exists("data"):
        os.makedirs("data")
    
    sanitized_target = target.replace("/", "_")
    return f"data/{type_prefix}_{sanitized_target}.csv"

def load_history(filepath):
    """Loads existing CSV history to prevent duplicates."""
    SEEN_URLS.clear() # Reset for new target
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            for url in df['URL']:
                SEEN_URLS.add(str(url))
            print(f"📚 Loaded {len(SEEN_URLS)} existing items from {filepath}")
        except:
            pass

def save_to_csv(items, filepath):
    """Appends new unique items to the specific CSV file."""
    if not items:
        return 0
    
    new_items = [i for i in items if i['URL'] not in SEEN_URLS]
    
    if new_items:
        df = pd.DataFrame(new_items)
        if os.path.exists(filepath):
            df.to_csv(filepath, mode='a', header=False, index=False)
        else:
            df.to_csv(filepath, index=False)
        
        for i in new_items:
            SEEN_URLS.add(i['URL'])
            
        print(f"✅ Saved {len(new_items)} new items to {filepath}")
        return len(new_items)
    else:
        print("💤 No new unique data found.")
        return 0

# --- MODE 1: LIVE MONITOR (RSS) ---
def run_monitor(target, is_user=False):
    prefix = "u" if is_user else "r"
    # Reddit RSS format: /r/sub/new.rss OR /user/name/submitted.rss
    if is_user:
        rss_url = f"https://www.reddit.com/user/{target}/submitted.rss?limit=100"
    else:
        rss_url = f"https://www.reddit.com/r/{target}/new.rss?limit=100"

    print(f"[{datetime.datetime.now()}] 📡 Checking RSS Feed for {prefix}/{target}...")
    
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(rss_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Blocked/Error (Status {response.status_code})")
            return

        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        posts = []
        
        for entry in root.findall('atom:entry', namespace):
            posts.append({
                "Date": entry.find('atom:published', namespace).text,
                "Title": entry.find('atom:title', namespace).text,
                "URL": entry.find('atom:link', namespace).attrib['href'],
                "Source": "Monitor-RSS"
            })
            
        save_to_csv(posts, get_file_path(target, prefix))

    except Exception as e:
        print(f"❌ Monitor Error: {e}")

# --- MODE 2: HISTORY SCRAPE (Mirrors) ---
def run_history(target, limit, is_user=False):
    prefix = "u" if is_user else "r"
    print(f"🚀 Starting HISTORY scrape for {prefix}/{target} (Target: {limit})...")
    
    filepath = get_file_path(target, prefix)
    load_history(filepath)
    
    after = None
    count = 0
    
    while count < limit:
        random.shuffle(MIRRORS)
        success = False
        
        for base_url in MIRRORS:
            try:
                # Mirror URL format differs slightly for users
                if is_user:
                    path = f"/user/{target}/submitted.json"
                else:
                    path = f"/r/{target}/new.json"
                
                target_url = f"{base_url}{path}?limit=100"
                if after:
                    target_url += f"&after={after}"
                
                print(f"📡 Requesting: {base_url} (Page Token: {after})")
                response = requests.get(target_url, headers={"User-Agent": USER_AGENT}, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    posts = []
                    
                    for child in data['data']['children']:
                        p = child['data']
                        date_str = datetime.datetime.fromtimestamp(p['created_utc']).isoformat()
                        posts.append({
                            "Date": date_str,
                            "Title": p['title'],
                            "URL": p.get('url_overridden_by_dest', p.get('url')),
                            "Source": "History-Mirror"
                        })
                    
                    saved = save_to_csv(posts, filepath)
                    count += saved
                    
                    after = data['data'].get('after')
                    if not after:
                        print("🏁 Reached end of history.")
                        return
                    
                    success = True
                    break 
            except:
                continue 
        
        if not success:
            print("❌ All mirrors failed. Waiting 30s...")
            time.sleep(30)
        else:
            print(f"⏸️ Cooling down (5s)... Total: {count}")
            time.sleep(5)

# --- CLI ARGS ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal Reddit Scraper (Open Source)")
    parser.add_argument("target", help="Name of Subreddit (e.g. 'python') or User (e.g. 'spez')")
    parser.add_argument("--mode", choices=["monitor", "history"], default="monitor", help="Run mode")
    parser.add_argument("--user", action="store_true", help="Flag if the target is a User, not a Subreddit")
    parser.add_argument("--limit", type=int, default=500, help="Max posts to scrape (History mode only)")
    
    args = parser.parse_args()
    
    # Pre-load history for monitor mode
    if args.mode == "monitor":
        prefix = "u" if args.user else "r"
        load_history(get_file_path(args.target, prefix))
        print(f"🤖 Monitoring {prefix}/{args.target} every 5 mins...")
        while True:
            run_monitor(args.target, args.user)
            time.sleep(300)
    else:
        run_history(args.target, args.limit, args.user)
