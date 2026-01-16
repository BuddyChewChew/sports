#!/usr/bin/env python3

import requests
from datetime import datetime, timezone
import os

# Configuration settings
BASE_URL = "https://streamed.pk/api/matches/all"
STREAM_API_BASE = "https://streamed.pk/api/stream"
DEFAULT_POSTER = 'https://streamed.pk/api/images/poster/fallback.webp'
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://streamed.pk/'
        })

    def get_real_stream_url(self, source_type, source_id):
        """Resolves the internal API link to a playable .m3u8 URL."""
        try:
            url = f"{STREAM_API_BASE}/{source_type}/{source_id}"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                # If data is a list, take the first source; if dict, take the url field
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get('url') or data[0].get('link')
                elif isinstance(data, dict):
                    return data.get('url') or data.get('link')
        except Exception as e:
            print(f"Error resolving stream {source_id}: {e}")
        return None

    def fetch_data(self):
        try:
            response = self.session.get(BASE_URL, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching matches: {e}")
            return None

    def should_skip_event(self, event_timestamp):
        if not event_timestamp:
            return False
        # Convert timestamp from milliseconds to seconds
        event_time = datetime.fromtimestamp(event_timestamp / 1000, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        hours_diff = (event_time - current_time).total_seconds() / 3600
        # Filter: keep matches starting in next 24h or started in last 4h
        return hours_diff < -4 or hours_diff > 24

    def generate_m3u(self):
        print("Scraping matches and resolving final stream URLs...")
        matches = self.fetch_data()
        
        if not matches:
            print("Failed to retrieve any match data.")
            return

        m3u_content = ["#EXTM3U", ""]

        for match in matches:
            # Check if match is live or upcoming
            if self.should_skip_event(match.get('date')):
                continue

            poster = f"https://streamed.pk{match['poster']}" if match.get('poster') else DEFAULT_POSTER
            category = match.get('category', 'Sports').replace('-', ' ').title()

            for source in match.get('sources', []):
                source_type = source.get('source')
                source_id = source.get('id')
                if not source_id or not source_type:
                    continue

                # Step 1: Get the actual .m3u8 link from the API
                real_url = self.get_real_stream_url(source_type, source_id)
                
                if not real_url:
                    continue

                # Step 2: Format for TiviMate
                event_time = datetime.fromtimestamp(match['date'] / 1000, tz=timezone.utc)
                display_name = f"{event_time.strftime('%I:%M %p')} - {match['title']} [{source_type.upper()}]"

                m3u_content.append(f'#EXTINF:-1 tvg-name="{match["title"]}" tvg-logo="{poster}" group-title="{category}",{display_name}')
                m3u_content.append(real_url)

        # Output the file to the repository
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        
        # Log results for debugging in GitHub Actions
        count = (len(m3u_content) - 2) // 2
        print(f"✅ Success: Generated {OUTPUT_FILE} with {count} active channels.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
