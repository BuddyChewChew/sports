#!/usr/bin/env python3
"""
StreamsPPV Catalog Scraper - Updated for new addon3.gstream.stream API
Generates an M3U file from the StreamsPPV Stremio addon catalog.

Changelog:
- Updated catalog endpoint from ppv-PPV to ppv-SPK
- Updated stream fetching to use /stream/ endpoint instead of /meta/.../videos
- Stream URL format changed to spk/playlist.m3u8 format
"""

import requests
import json
import time
from datetime import datetime
import urllib.parse

# Configuration - UPDATED endpoints
ADDON_BASE_URL = "https://addon3.gstream.stream"
CATALOG_URL = f"{ADDON_BASE_URL}/catalog/StreamsPPV/ppv-SPK.json"  # Changed from ppv-PPV
STREAM_BASE_URL = f"{ADDON_BASE_URL}/stream/StreamsPPV"  # New: stream endpoint instead of meta
OUTPUT_FILE = "ppv_proxy.m3u"

# Categories to include (matching the addon's genres from manifest)
WANTED_CATEGORIES = [
    "American Football",
    "Australian Football", 
    "Baseball",
    "Basketball", 
    "Combat Sports", 
    "Cricket",
    "Darts",
    "Football", 
    "Hockey",
    "Motorsports",
    "Rugby",
    "Tennis",
    "Miscellaneous",
    "Channels"
]

def fetch_catalog():
    """Fetch the PPV catalog from the addon"""
    print(f"Fetching catalog from {CATALOG_URL}...")
    try:
        resp = requests.get(CATALOG_URL, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })
        resp.raise_for_status()
        data = resp.json()
        metas = data.get("metas", [])
        print(f"✅ Catalog fetched: {len(metas)} items")
        return metas
    except Exception as e:
        print(f"❌ Error fetching catalog: {e}")
        return []

def fetch_streams(item_id):
    """Fetch streams for an item using the /stream/ endpoint"""
    # URL encode the item_id properly
    encoded_id = urllib.parse.quote(item_id, safe='')
    url = f"{STREAM_BASE_URL}/{encoded_id}.json"
    
    try:
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        })
        if resp.status_code == 200:
            data = resp.json()
            streams = data.get("streams", [])
            return streams
        else:
            return []
    except Exception as e:
        print(f"  ⚠️ Error fetching streams: {e}")
        return []

def main():
    items = fetch_catalog()
    print(f"Found {len(items)} items in catalog.")
    
    if not items:
        print("❌ No items found, exiting.")
        return
    
    m3u_lines = ["#EXTM3U"]
    count = 0
    skipped = 0

    for item in items:
        item_id = item.get("id", "")
        name = item.get("name", "Unknown")
        genres = item.get("genres", [])
        poster = item.get("poster", "")
        release_info = item.get("releaseInfo", "")
        
        # Get category (first genre)
        category = genres[0] if genres else "Unknown"
        
        # Filter by wanted categories
        if category not in WANTED_CATEGORIES:
            skipped += 1
            continue
        
        print(f"Processing: {name} ({category}) - {release_info}")
        
        # Fetch streams for this item
        streams = fetch_streams(item_id)
        
        if not streams:
            print(f"  ❌ No streams found")
            continue
        
        # Process each stream
        for stream in streams:
            stream_url = stream.get("url", "")
            stream_title = stream.get("title", "")
            
            if not stream_url:
                continue
            
            # Determine status prefix based on releaseInfo
            status_prefix = ""
            if "Live" in release_info:
                status_prefix = "[LIVE] "
            elif "Upcoming" in release_info:
                status_prefix = "[UPCOMING] "
            elif "Watch Now" in release_info:
                status_prefix = ""  # Channels don't need prefix
            
            # Build the display name
            # Include stream title info if it's different from the item name
            if stream_title and stream_title != name:
                display_name = f"{status_prefix}{name} - {stream_title}"
            else:
                display_name = f"{status_prefix}{name}"
            
            # Add timestamp for events
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
            full_name = f"{display_name} [{timestamp}]"
            
            # Construct M3U entry
            entry = (
                f'#EXTINF:-1 tvg-logo="{poster}" '
                f'group-title="{category}" '
                f'tvg-id="{name}" '
                f'tvg-name="{full_name}",'
                f'{full_name}\n'
                f'{stream_url}'
            )
            m3u_lines.append(entry)
            count += 1
            print(f"  ✅ Added: {stream_title or 'stream'}")
        
        # Be nice to the server
        time.sleep(0.15)

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    
    print(f"\n{'='*50}")
    print(f"✅ Saved {count} streams to {OUTPUT_FILE}")
    print(f"📊 Processed: {len(items) - skipped} items, Skipped: {skipped}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
