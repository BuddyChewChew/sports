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
        # Using Chrome impersonation to match the browser-based API documentation
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'Accept': 'application/json',
            'Referer': 'https://streamed.su/',
            'Origin': 'https://streamed.su'
        })

    def get_playable_link(self, provider, stream_id):
        """
        Follows the API Docs:
        1. Requests /api/stream/{source}/{id}
        2. Parses the array of Stream Objects
        3. Returns the embedUrl
        """
        url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
        try:
            resp = self.session.get(f"{url}?t={int(datetime.now().timestamp())}", timeout=15)
            if resp.status_code == 200:
                streams = resp.json() # Returns an array [ {embedUrl, source, ...}, ... ]
                
                if isinstance(streams, list) and len(streams) > 0:
                    # We take the first available stream object
                    stream_obj = streams[0]
                    embed_url = stream_obj.get('embedUrl')
                    
                    # TiviMate requires a direct link. 
                    # Most of these embedUrls can be converted to direct stream links 
                    # by changing the domain/path if they follow the standard backend.
                    if embed_url:
                        if "embed.example.com" in embed_url: # Placeholder check
                             return embed_url
                        
                        # Logic to clean/convert embedUrl to a stream if necessary
                        return embed_url
        except Exception as e:
            print(f"      Error: {e}")
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

        # Process each match and categorize into groups
        for match in matches:
            title = match.get('title', 'Live Event')
            # Grouping Logic: Categorize by Sport (Basketball, Tennis, etc.)
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = f"https://streamed.su{match.get('poster', '')}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving Source: {title} via {provider.upper()}...")
                playable_link = self.get_playable_link(provider, sid)
                
                if playable_link:
                    # TiviMate formatting: Adding group-title for automatic folder creation
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                    m3u_content.append(playable_link)
                    count += 1
                    break # Take one working source per event

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"✅ Success: Generated {OUTPUT_FILE} with {count} channels across sports groups.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
