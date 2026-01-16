#!/usr/bin/env python3

from curl_cffi import requests # specialized library for bot-bypass
import json
import os
from datetime import datetime

# Configuration
RAW_JSON_URL = "https://raw.githubusercontent.com/BuddyChewChew/sports/refs/heads/main/live.json"
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        # We use a session with Chrome impersonation to bypass bot detection
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'Accept': 'application/json',
            'Referer': 'https://streamed.su/watch',
            'Origin': 'https://streamed.su'
        })

    def get_resolved_url(self, provider, stream_id):
        """Resolves the ID into a playable .m3u8 link using browser-impersonation."""
        try:
            url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
            # Adding a timestamp 't' parameter to prevent server-side caching
            resp = self.session.get(f"{url}?t={int(datetime.now().timestamp())}", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Handle cases where the response is a list or a dictionary
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    return item if isinstance(item, str) else item.get('url')
                elif isinstance(data, dict):
                    return data.get('url')
        except Exception:
            pass
        return None

    def generate_m3u(self):
        print(f"Reading live data from repository...")
        try:
            # We fetch the JSON data you've already successfully saved
            response = self.session.get(f"{RAW_JSON_URL}?t={int(datetime.now().timestamp())}")
            response.raise_for_status()
            matches = response.json()
            
            if not matches:
                print("⚠️ No matches found in live.json.")
                return

        except Exception as e:
            print(f"❌ Error reading live.json: {e}")
            return

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Live Event')
            # Extract category and format for TiviMate groups
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = f"https://streamed.su{match.get('poster', '')}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title} ({provider.upper()})...")
                real_link = self.get_resolved_url(provider, sid)
                
                if real_link:
                    # m3u entry with group-title and logo
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                    m3u_content.append(real_link)
                    count += 1
                    break # Use the first working source available

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"✅ Success: Generated {OUTPUT_FILE} with {count} active channels.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
