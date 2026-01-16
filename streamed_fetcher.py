#!/usr/bin/env python3

from curl_cffi import requests
import json
import os
from datetime import datetime

# Configuration
RAW_JSON_URL = "https://raw.githubusercontent.com/BuddyChewChew/sports/refs/heads/main/live.json"
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        # chrome120 impersonation is key to bypassing the TLS block
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'Accept': 'application/json',
            'Referer': 'https://streamed.su/',
            'Origin': 'https://streamed.su'
        })

    def get_playable_link(self, provider, stream_id):
        """Fetches the stream array and extracts the embed URL."""
        url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
        try:
            resp = self.session.get(f"{url}?t={int(datetime.now().timestamp())}", timeout=15)
            if resp.status_code == 200:
                streams = resp.json() 
                if isinstance(streams, list) and len(streams) > 0:
                    # Taking the first stream object from the array
                    return streams[0].get('embedUrl')
        except Exception:
            pass
        return None

    def generate_m3u(self):
        print(f"Reading live data from repository...")
        try:
            response = self.session.get(f"{RAW_JSON_URL}?t={int(datetime.now().timestamp())}")
            response.raise_for_status()
            matches = response.json()
        except Exception as e:
            print(f"❌ Error loading live.json: {e}")
            return

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Live Event')
            # Categorization for TiviMate Groups
            category = match.get('category', 'Sports').replace('-', ' ').title()
            
            # Ensure the poster URL is absolute
            poster = match.get('poster', '')
            if poster.startswith('/'):
                poster = f"https://streamed.su{poster}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title} ({provider.upper()})...")
                link = self.get_playable_link(provider, sid)
                
                if link:
                    # Final M3U structure with Group-Title and Logo
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                    m3u_content.append(link)
                    count += 1
                    break 

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"✅ Success: Generated {OUTPUT_FILE} with {count} channels across sports groups.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
