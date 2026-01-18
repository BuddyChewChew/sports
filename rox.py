import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

# Integrated Settings
BASE_URL = "https://roxiestreams.live"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"

TV_INFO = {
    "ppv": ("PPV.EVENTS.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/ppv2.png?raw=true", "PPV Events"),
    "soccer": ("Soccer.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/football.png?raw=true", "Soccer"),
    "ufc": ("UFC.Fight.Pass.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/mma.png?raw=true", "Combat Sports"),
    "fighting": ("Combat.Sports.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/boxing.png?raw=true", "Combat Sports"),
    "nfl": ("Football.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nfl.png?raw=true", "Football"),
    "nhl": ("NHL.Hockey.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/hockey.png?raw=true", "Hockey"),
    "nba": ("NBA.Basketball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nba.png?raw=true", "Basketball"),
    "mlb": ("MLB.Baseball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/baseball.png?raw=true", "Baseball"),
    "motorsports": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports")
}

DEFAULT_LOGO = "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/default.png?raw=true"
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': BASE_URL
})

M3U8_REGEX = re.compile(r'https?://[^\s"\'<>`]+\.m3u8')
logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_tv_info(url, title=""):
    combined = (url + title).lower()
    for key, (epg_id, logo, group) in TV_INFO.items():
        if key in combined: return epg_id, logo, group
    return "Sports.Rox.us", DEFAULT_LOGO, "General Sports"

def extract_m3u8_deep(url):
    """Scrapes the main page and follows common player patterns."""
    links = set()
    try:
        r = SESSION.get(url, timeout=10)
        r.encoding = 'utf-8'
        links.update(M3U8_REGEX.findall(r.text))
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Look for the mirror buttons/links and iframes
        tags = soup.find_all(['iframe', 'a', 'source'], src=True) or soup.find_all('iframe')
        
        for tag in tags:
            src = tag.get('src') or tag.get('href')
            if not src: continue
            
            if any(x in src for x in ['alfirdaus', 'roxiestreams', 'embed', 'player', 'nfl-streams']):
                target_url = urljoin(url, src)
                try:
                    # Avoid infinite loops on the same page
                    if target_url != url:
                        if_r = SESSION.get(target_url, timeout=5)
                        links.update(M3U8_REGEX.findall(if_r.text))
                except: continue
    except: pass
    return links

def main():
    playlist = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    seen_links = set()
    event_pages = set()

    # Manual NFL priority scan based on your links
    for i in range(1, 6):
        event_pages.add((f"{BASE_URL}/nfl-streams-{i}", f"NFL Game Mirror {i}"))

    # Standard Category Scan
    sections = [BASE_URL, f"{BASE_URL}/nfl", f"{BASE_URL}/nba", f"{BASE_URL}/soccer", f"{BASE_URL}/fighting"]
    for sec in sections:
        try:
            r = SESSION.get(sec, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(x in href for x in ['/stream/', 'nfl-streams']):
                    event_pages.add((urljoin(BASE_URL, href), a.get_text(strip=True) or "Live Event"))
        except: continue

    for url, title in event_pages:
        m3u8s = extract_m3u8_deep(url)
        mirror_count = 1
        for link in m3u8s:
            if link not in seen_links:
                try:
                    if SESSION.head(link, timeout=3).status_code == 200:
                        eid, logo, grp = get_tv_info(url, title)
                        display_name = title if mirror_count == 1 else f"{title} (Mirror {mirror_count})"
                        playlist.append(f'#EXTINF:-1 tvg-id="{eid}" tvg-logo="{logo}" group-title="{grp}",{display_name}')
                        playlist.append(link)
                        seen_links.add(link)
                        mirror_count += 1
                        logging.info(f"Added: {display_name}")
                except: pass

    with open("Roxiestreams.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(playlist))

if __name__ == "__main__":
    main()
