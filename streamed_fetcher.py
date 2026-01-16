#!/usr/bin/env python3

import requests
from datetime import datetime, timezone
import os

# Configuration settings
BASE_URL = "https://streamed.pk/api/matches/all"
DEFAULT_POSTER = 'https://streamed.pk/api/images/poster/fallback.webp'
OUTPUT_FILE = 'streamed.m3u'

class StreamFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        })

    def fetch_data(self):
        """Fetches the match data from the API."""
        try:
            response = self.session.get(BASE_URL, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching data: {e}")
            return None

    def should_skip_event(self, event_timestamp):
        """Filters events: shows matches from 4 hours ago up to 24 hours ahead."""
        if not event_timestamp:
            return False
        event_time = datetime.fromtimestamp(event_timestamp / 1000, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        hours_diff = (event_time - current_time).total_seconds() / 3600
        return hours_diff < -4 or hours_diff > 24

    def generate_m3u(self):
        print(f"Fetching matches from {BASE_URL}...")
        matches = self.fetch_data()
        
        if not matches:
            print("No data received.")
            return

        m3u_content = ["#EXTM3U", ""]

        for match in matches:
            if self.should_skip_event(match.get('date')):
                continue

            poster = f"https://streamed.pk{match['poster']}" if match.get('poster') else DEFAULT_POSTER
            category = "24/7 Live" if match.get('date', 0) == 0 else match.get('category', 'Unknown')
            category_formatted = category if category == "24/7 Live" else category.replace('-', ' ').title()

            for source in match.get('sources', []):
                source_name = source.get('source', '').title()
                source_id = source.get('id')
                if not source_id:
                    continue

                if category == "24/7 Live":
                    display_name = match['title']
                else:
                    event_time = datetime.fromtimestamp(match['date'] / 1000, tz=timezone.utc)
                    formatted_time = event_time.strftime('%I:%M %p')
                    formatted_date = event_time.strftime('%d/%m/%Y')
                    display_name = f"{formatted_time} - {match['title']} [{source_name}] - ({formatted_date})"

                # TiviMate compatible tags
                m3u_content.append(f'#EXTINF:-1 tvg-name="{match["title"]}" tvg-logo="{poster}" group-title="{category_formatted}",{display_name}')
                m3u_content.append(f'https://streamed.pk/api/stream/{source["source"]}/{source_id}')

        # Write to the local directory
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_content))
        print(f"✅ Created {OUTPUT_FILE} successfully.")

if __name__ == "__main__":
    fetcher = StreamFetcher()
    fetcher.generate_m3u()
