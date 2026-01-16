#!/usr/bin/env python3

import requests
import json
import os

# Configuration
INPUT_FILE = 'live.json'
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://streamed.su',
            'Referer': 'https://streamed.su/watch'
        })

    def get_resolved_url(self, provider, stream_id):
        """Resolves the source ID into a playable .m3u8 link."""
        try:
            url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    item = data[0]
                    return item if isinstance(item, str) else item.get('url')
                elif isinstance(data, dict):
                    return data.get('url')
        except:
            pass
        return None

    def generate_m3u(self):
        if not os.path.exists(INPUT_FILE):
            print(f"❌ Error: {INPUT_FILE} not found in repository. Please upload it.")
            return

        print(f"Processing matches from {INPUT_FILE}...")
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                matches = json.load(f)
        except Exception as e:
            print(f"❌ Error reading JSON: {e}")
            return

        m3u_content = ["#EXTM3U", ""]
        count = 0

        for match in matches:
            title = match.get('title', 'Live Event')
            category = match.get('category', 'Sports').title()
            poster = f"https://streamed.su{match.get('poster', '')}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title}...")
                real_link = self.get_resolved_url(provider, sid)
                
                if real_link:
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                    m3u_content.append(real_link)
                    count += 1
                    break 

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"✅ Success: Created {OUTPUT_FILE} with {count} active channels.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
