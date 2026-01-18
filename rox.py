import logging
from requests_html import HTMLSession
import re

# Integrated Settings & Constants
BASE_URL = "https://roxiestreams.live"
EPG_URL = "https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"

CATEGORIES = [
    f"{BASE_URL}/nfl", f"{BASE_URL}/soccer", f"{BASE_URL}/mlb",
    f"{BASE_URL}/nba", f"{BASE_URL}/nhl", f"{BASE_URL}/fighting",
    f"{BASE_URL}/motorsports"
]

TV_INFO = {
    "soccer": ("Soccer.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/football.png?raw=true", "Soccer"),
    "nfl": ("Football.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nfl.png?raw=true", "Football"),
    "nba": ("NBA.Basketball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nba.png?raw=true", "Basketball"),
    "mlb": ("MLB.Baseball.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/baseball.png?raw=true", "Baseball"),
    "nhl": ("NHL.Hockey.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/nhl.png?raw=true", "Hockey"),
    "fighting": ("Combat.Sports.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/boxing.png?raw=true", "Combat Sports"),
    "motorsports": ("Racing.Dummy.us", "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/f1.png?raw=true", "Motorsports")
}

DEFAULT_LOGO = "https://github.com/BuddyChewChew/sports/blob/main/sports%20logos/default.png?raw=true"
M3U8_REGEX = re.compile(r'https?://[^\s"\'<>`]+\.m3u8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_tv_info(url):
    for key, (epg_id, logo, group) in TV_INFO.items():
        if key in url.lower(): return epg_id, logo, group
    return "Sports.Rox.us", DEFAULT_LOGO, "General Sports"

def main():
    session = HTMLSession()
    playlist = [f'#EXTM3U x-tvg-url="{EPG_URL}"']
    seen_streams = set()

    for cat_url in CATEGORIES:
        logging.info(f"Scanning Category: {cat_url}")
        try:
            r = session.get(cat_url)
            # Find the table and all links within it
            table = r.html.find('#eventsTable', first=True)
            if not table:
                logging.warning(f"No table found at {cat_url}")
                continue

            links = table.find('a')
            for link in links:
                event_title = link.text.strip()
                event_url = list(link.absolute_links)[0]
                
                logging.info(f"Opening event: {event_title}")
                event_page = session.get(event_url)
                # Render JS to find hidden m3u8
                event_page.html.render(timeout=20)
                
                m3u8_links = M3U8_REGEX.findall(event_page.html.html)
                for m3u8 in m3u8_links:
                    if m3u8 not in seen_streams:
                        eid, logo, grp = get_tv_info(cat_url)
                        playlist.append(f'#EXTINF:-1 tvg-id="{eid}" tvg-logo="{logo}" group-title="{grp}",{event_title}')
                        playlist.append(m3u8)
                        seen_streams.add(m3u8)
                        logging.info(f"Found Stream: {event_title}")
        except Exception as e:
            logging.error(f"Error at {cat_url}: {e}")

    with open("Roxiestreams.m3u", "w", encoding="utf-8") as f:
        f.write("\n".join(playlist))

if __name__ == "__main__":
    main()
