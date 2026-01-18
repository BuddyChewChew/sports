import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.exceptions import RequestException
import logging

BASE_URL = "https://roxiestreams.live"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"

# Enhanced Mapping: (EPG_ID, Logo_URL, Group_Name)
TV_INFO = {
    "ppv": ("PPV.EVENTS.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/ppv2.png?raw=true", "PPV Events"),
    "soccer": ("Soccer.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/football.png?raw=true", "Soccer"),
    "ufc": ("UFC.Fight.Pass.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/mma.png?raw=true", "Combat Sports"),
    "fighting": ("Combat.Sports.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/boxing.png?raw=true", "Combat Sports"),
    "nfl": ("Football.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nfl.png?raw=true", "Football"),
    "nhl": ("NHL.Hockey.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/hockey.png?raw=true", "Hockey"),
    "hockey": ("NHL.Hockey.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nhl.png?raw=true", "Hockey"),
    "f1": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports"),
    "motorsports": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports"),
    "wwe": ("PPV.EVENTS.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/wwe.png?raw=true", "Wrestling"),
    "nba": ("NBA.Basketball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nba.png?raw=true", "Basketball"),
    "mlb": ("MLB.Baseball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/baseball.png?raw=true", "Baseball")
}

DEFAULT_LOGO = "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/default.png?raw=true"
DEFAULT_GROUP = "General Sports"
DISCOVERY_KEYWORDS = list(TV_INFO.keys()) + ['streams']
SECTION_BLOCKLIST = ['olympia']

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Referer': BASE_URL
})

M3U8_REGEX = re.compile(r'https?://[^\s"\'<>`]+\.m3u8')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_tv_info(url, title=""):
    """Determines logo, EPG ID, and Group Name by checking both URL and Event Title."""
    combined_text = (url + title).lower()
    for key, (epg_id, logo, group) in TV_INFO.items():
        if key in combined_text:
            return epg_id, logo, group
    return "Sports.Rox.us", DEFAULT_LOGO, DEFAULT_GROUP

def discover_sections(base_url):
    """Finds top-level categories like /nba, /nhl, etc."""
    sections_found = []
    try:
        resp = SESSION.get(base_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        discovered_urls = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            title = a_tag.get_text(strip=True)
            if not href or href.startswith(('#', 'javascript:', 'mailto:')) or not title:
                continue
            abs_url = urljoin(base_url, href)
            if any(blocked in abs_url.lower() for blocked in SECTION_BLOCKLIST):
                continue
            if (urlparse(abs_url).netloc == urlparse(base_url).netloc and
                    any(keyword in abs_url.lower() for keyword in DISCOVERY_KEYWORDS)):
                if abs_url not in discovered_urls:
                    discovered_urls.add(abs_url)
                    sections_found.append((abs_url, title))
    except Exception as e:
        logging.error(f"Discovery error: {e}")
    return sections_found

def discover_event_links(section_url):
    """Finds individual event pages within a section."""
    events = set()
    try:
        resp = SESSION.get(section_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        event_table = soup.find('table', id='eventsTable') 
        if event_table:
            for a_tag in event_table.find_all('a', href=True):
                href = a_tag['href']
                title = a_tag.get_text(strip=True)
                if href and title:
                    abs_url = urljoin(section_url, href)
                    if abs_url.startswith(BASE_URL):
                        events.add((abs_url, title))
    except Exception:
        pass
    return events

def extract_m3u8_links(page_url):
    """Scrapes raw HTML for .m3u8 links."""
    links = set()
    try:
        resp = SESSION.get(page_url, timeout=10)
        resp.raise_for_status()
        links.update(M3U8_REGEX.findall(resp.text))
    except Exception:
        pass
    return links

def check_stream_status(m3u8_url):
    """Verifies link is active."""
    try:
        resp = SESSION.head(m3u8_url, timeout=5, allow_redirects=True)
        return resp.status_code == 200
    except Exception:
        return False

def main():
    playlist_lines = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    sections = discover_sections(BASE_URL)
    
    seen_links = set()
    title_tracker = {}

    for section_url, section_title in sections:
        event_links = discover_event_links(section_url)
        # If no sub-links, scrape the section page itself
        pages = event_links if event_links else {(section_url, section_title)}

        for event_url, event_title in pages:
            # Now returns 3 items: ID, Logo, and the Group name
            tv_id, logo, group_name = get_tv_info(event_url, event_title)
            m3u8_links = extract_m3u8_links(event_url)
            
            for link in m3u8_links:
                if link in seen_links:
                    continue
                
                if check_stream_status(link):
                    # Logic to identify and label mirrors
                    title_tracker[event_title] = title_tracker.get(event_title, 0) + 1
                    count = title_tracker[event_title]
                    
                    display_name = event_title if count == 1 else f"{event_title} (Mirror {count-1})"
                    
                    # group-title is now set to group_name instead of a hardcoded string
                    playlist_lines.append(f'#EXTINF:-1 tvg-id="{tv_id}" tvg-logo="{logo}" group-title="{group_name}",{display_name}')
                    playlist_lines.append(link)
                    seen_links.add(link)

    with open("Roxiestreams.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(playlist_lines))
    logging.info(f"Playlist updated. Found {len(seen_links)} unique streams grouped by category.")

if __name__ == "__main__":
    main()
