import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

# Integrated Settings & Constants
BASE_URL = "https://roxiestreams.live"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"

# The specific categories you provided
CATEGORIES = [
    f"{BASE_URL}/nfl",
    f"{BASE_URL}/soccer",
    f"{BASE_URL}/mlb",
    f"{BASE_URL}/nba",
    f"{BASE_URL}/nhl",
    f"{BASE_URL}/fighting",
    f"{BASE_URL}/motorsports"
]

TV_INFO = {
    "ppv": ("PPV.EVENTS.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/ppv2.png?raw=true", "PPV Events"),
    "soccer": ("Soccer.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/football.png?raw=true", "Soccer"),
    "ufc": ("UFC.Fight.Pass.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/mma.png?raw=true", "Combat Sports"),
    "fighting": ("Combat.Sports.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/boxing.png?raw=true", "Combat Sports"),
    "nfl": ("Football.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nfl.png?raw=true", "Football"),
    "nhl": ("NHL.Hockey.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nhl.png?raw=true", "Hockey"),
    "f1": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports"),
    "motorsports": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports"),
    "wwe": ("PPV.EVENTS.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/wwe.png?raw=true", "Wrestling"),
    "nba": ("NBA.Basketball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nba.png?raw=true", "Basketball"),
    "mlb": ("MLB.Baseball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/baseball.png?raw=true", "Baseball")
}

DEFAULT_LOGO = "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/default.png?raw=true"
DEFAULT_GROUP = "General Sports"

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': BASE_URL
})

M3U8_REGEX = re.compile(r'https?://[^\s"\'<>`]+\.m3u8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_tv_info(url, title=""):
    combined_text = (url + title).lower()
    for key, (epg_id, logo, group) in TV_INFO.items():
        if key in combined_text:
            return epg_id, logo, group
    return "Sports.Rox.us", DEFAULT_LOGO, DEFAULT_GROUP

def extract_event_links(cat_url):
    """Finds links to individual game players within a category page."""
    events = set()
    try:
        resp = SESSION.get(cat_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for links that contain team vs team or game names
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            title = a_tag.get_text(strip=True)
            
            # Filter: Links should be internal and have a title (e.g. "Cowboys vs Giants")
            if href and title and not href.endswith(('/nfl', '/nba', '/mlb', '/nhl', '/soccer')):
                abs_url = urljoin(BASE_URL, href)
                if abs_url.startswith(BASE_URL):
                    events.add((abs_url, title))
    except Exception as e:
        logging.error(f"Error reading category {cat_url}: {e}")
    return events

def extract_m3u8_links(page_url):
    """Extracts .m3u8 from the actual stream/player page."""
    links = set()
    try:
        resp = SESSION.get(page_url, timeout=10)
        resp.raise_for_status()
        
        # Standard Regex for m3u8
        links.update(M3U8_REGEX.findall(resp.text))
        
        # Obfuscated script source check
        scripts = re.findall(r'file:\s*["\'](.*?\.m3u8.*?)["\']', resp.text)
        links.update(scripts)
        
        # Check for iframes that might host the player
        soup = BeautifulSoup(resp.text, 'html.parser')
        for iframe in soup.find_all('iframe', src=True):
            iframe_url = urljoin(page_url, iframe['src'])
            # Briefly check iframe content if it's on the same domain
            if urlparse(iframe_url).netloc == urlparse(BASE_URL).netloc:
                if_resp = SESSION.get(iframe_url, timeout=5)
                links.update(M3U8_REGEX.findall(if_resp.text))
                
    except Exception:
        pass
    return links

def check_stream_status(m3u8_url):
    try:
        resp = SESSION.get(m3u8_url, timeout=5, stream=True)
        return resp.status_code == 200
    except Exception:
        return False

def main():
    playlist_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    seen_links = set()
    title_tracker = {}

    for cat_url in CATEGORIES:
        logging.info(f"Processing Category: {cat_url}")
        events = extract_event_links(cat_url)
        
        for event_url, event_title in events:
            tv_id, logo, group_name = get_tv_info(event_url, event_title)
            m3u8_links = extract_m3u8_links(event_url)
            
            for link in m3u8_links:
                if link in seen_links:
                    continue
                
                if check_stream_status(link):
                    title_tracker[event_title] = title_tracker.get(event_title, 0) + 1
                    count = title_tracker[event_title]
                    display_name = event_title if count == 1 else f"{event_title} (Mirror {count-1})"
                    
                    playlist_lines.append(f'#EXTINF:-1 tvg-id="{tv_id}" tvg-logo="{logo}" group-title="{group_name}",{display_name}')
                    playlist_lines.append(link)
                    seen_links.add(link)
                    logging.info(f"Found: {display_name}")

    with open("Roxiestreams.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(playlist_lines))
    
    logging.info(f"Playlist Generation Complete. Total streams: {len(seen_links)}")

if __name__ == "__main__":
    main()
