#!/usr/bin/env python3

from curl_cffi import requests
import json
import re
import os
from datetime import datetime

# Configuration
RAW_JSON_URL = "https://raw.githubusercontent.com/BuddyChewChew/sports/refs/heads/main/live.json"
STREAM_API_BASE = "https://streamed.su/api/stream"
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        # Impersonate a real browser to bypass anti-scraping on the embed site
        self.session = requests.Session(impersonate="chrome120")
        self.session.headers.update({
            'Referer': 'https://streamed.su/',
            'Origin': 'https://streamed.su',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def scrape_direct_link(self, embed_url):
        """Extracts the direct .m3u8 link from the Clappr player configuration."""
        try:
            resp = self.session.get(embed_url, timeout=15)
            if resp.status_code == 200:
                html = resp.text
                
                # Specifically targeting the Clappr 'source:' definition
                # This finds the lb*.strmd.top pattern you identified
                patterns = [
                    r'source\s*:\s*["\'](https?://lb[0-9]+\.strmd\.top/secure/[^"\']+\.m3u8[^"\']*)["\']',
                    r'(https?://lb[0-9]+\.strmd\.top/secure/[^"\']+\.m3u8[^\s"\'\\]*)',
                    r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']'
                ]
                
                for pattern in patterns:
                    found = re.findall(pattern, html)
                    if found:
                        # Unescape and return the first valid link found
                        clean_link = found[0].replace('\\/', '/').replace('\\', '')
                        return clean_link
        except Exception as e:
            print(f"      Scrape Error: {e}")
        return None

    def get_resolved_url(self, provider, stream_id):
        """Calls the stream API to get the embed URL, then scrapes the video file."""
        api_url = f"{STREAM_API_BASE}/{provider}/{stream_id}"
        try:
            # Add a timestamp to bypass API caching
            resp = self.session.get(f"{api_url}?t={int(datetime.now().timestamp())}", timeout=10)
            if resp.status_code == 200:
                streams = resp.json()
                if isinstance(streams, list) and len(streams) > 0:
                    embed_url = streams[0].get('embedUrl')
                    if embed_url:
                        if embed_url.startswith('//'):
                            embed_url = 'https:' + embed_url
                        return self.scrape_direct_link(embed_url)
        except Exception:
            pass
        return None

    def generate_m3u(self):
        print(f"--- Starting TiviMate-Ready Stream Scraper ---")
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
            # Normalize category for TiviMate groups
            category = match.get('category', 'Sports').replace('-', ' ').title()
            poster = match.get('poster', '')
            if poster.startswith('/'):
                poster = f"https://streamed.su{poster}"

            for source in match.get('sources', []):
                provider = source.get('source')
                sid = source.get('id')
                
                print(f"Resolving: {title} ({provider.upper()})...")
                direct_video_link = self.get_resolved_url(provider, sid)
                
                if direct_video_link:
                    # Final M3U structure with required TVG tags
                    m3u_content.append(f'#EXTINF:-1 tvg-logo="{poster}" group-title="{category}",{title} ({provider.upper()})')
                    m3u_content.append(direct_video_link)
                    count += 1
                    break 

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        print(f"\n✅ Success: Generated {OUTPUT_FILE} with {count} playable m3u8 links.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
