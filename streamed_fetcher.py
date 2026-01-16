#!/usr/bin/env python3

import requests
import os
from datetime import datetime, timezone

# Configuration
LIVE_API_URL = "https://streamed.su/api/matches/live"
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://streamed.su',
            'Referer': 'https://streamed.su/watch',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })

    def get_resolved_url(self, provider, stream_id):
        """Resolves the internal ID into a direct, playable m3u8 stream link."""
        try:
            url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                
                # FIX: Handle cases where data is a list instead of a dictionary
                if isinstance(data, list):
                    if not data: return None
                    item = data[0]
                    # If list contains strings, return the string. If objects, use .get()
                    return item if isinstance(item, str) else item.get('url') or item.get('link')
                
                # If data is a dictionary
                return data.get('url') or data.get('link')
        except Exception as e:
            print(f"Error resolving stream {stream_id}: {e}")
        return None

    def generate_m3u(self):
        print(f"Polling LIVE matches from: {LIVE_API_URL}")
        try:
            response = self.session.get(f"{LIVE_API_URL}?t={int(datetime.now().timestamp())}", timeout=20)
            response.raise_for_status()
            live_matches = response.json()
        except Exception as e:
            print(f"Failed to fetch live data: {e}")
            return

        m3u_content = ["#EXTM3U", ""]
        channel_count = 0

        for match in live_matches:
            title = match.get('title', 'Live Event')
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = f"https://streamed.su{match.get('poster', '')}"

            for source in match.get('sources', []):
                provider = source.get('source')
                stream_id = source.get('id')
                if not provider or not stream_id: continue

                playable_url = self.get_resolved_url(provider, stream_id)
                
                if playable_url:
                    display_name = f"{title} [{provider.upper()}]"
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{display_name}')
                    m3u_content.append(playable_url)
                    channel_count += 1
                    break

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"✅ Success: Generated {OUTPUT_FILE} with {channel_count} live channels.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
